const clamp=(v,lo=0,hi=1)=>Math.min(Math.max(Number(v),lo),hi);
const round=(n,d=2)=>{const p=10**d;return Math.round((Number(n)+Number.EPSILON)*p)/p;};
const mean=xs=>xs.reduce((a,b)=>a+b,0)/Math.max(xs.length,1);

function linreg(xs,ys){
  if(xs.length<2)return {slope:0,intercept:ys[0]??0,r2:0};
  const xm=mean(xs), ym=mean(ys);
  const num=xs.reduce((s,x,i)=>s+(x-xm)*(ys[i]-ym),0);
  const den=xs.reduce((s,x)=>s+(x-xm)**2,0);
  const slope=den?num/den:0, intercept=ym-slope*xm;
  const ssTot=ys.reduce((s,y)=>s+(y-ym)**2,0);
  const ssRes=ys.reduce((s,y,i)=>s+(y-(slope*xs[i]+intercept))**2,0);
  const r2=ssTot?Math.max(0,Math.min(1,1-ssRes/ssTot)):0;
  return {slope,intercept,r2};
}

export function runP1({productId,currentPrice,observations,now=new Date(),maxAgeHours=72}){
  const cutoff=now.getTime()-maxAgeHours*3600_000;
  const valid=(observations||[]).map(o=>({
    store_name:String(o.store_name??o.store??"unknown"),
    price:Number(o.price),
    observed_at:String(o.observed_at??o.last_checked??""),
    source:String(o.source??"store-observation")
  })).filter(o=>Number.isFinite(o.price)&&o.price>0&&o.observed_at&&Date.parse(o.observed_at)>=cutoff);
  if(!valid.length) return {status:"INSUFFICIENT_DATA",product_id:productId,observations:[],market_min:null,market_max:null,market_average:null,market_position_pct:null,observed_at:now.toISOString(),source_version:"P1-v1",confidence:0.1};
  const prices=valid.map(x=>x.price), avg=mean(prices);
  return {
    status:"OK",product_id:productId,observations:valid,
    market_min:round(Math.min(...prices)),market_max:round(Math.max(...prices)),market_average:round(avg),
    market_position_pct:round(avg?((Number(currentPrice)-avg)/avg)*100:0,2),
    observed_at:now.toISOString(),source_version:"P1-v1",
    confidence:round(Math.min(.95,.55+.08*valid.length),2)
  };
}

export function runP2({productId,unitCost,marginFloorPct,variableFeesPerUnit=0,currency="ZAR"}){
  const cost=Number(unitCost)+Number(variableFeesPerUnit||0);
  const floor=Number(marginFloorPct);
  if(!(cost>=0)||!(floor>=0&&floor<1)) return {status:"INVALID_INPUT",product_id:productId,source_version:"P2-v1",confidence:0};
  const minPrice=cost/(1-floor);
  return {
    status:"OK",product_id:productId,effective_unit_cost:round(cost,4),margin_floor_pct:floor,
    minimum_price:round(minPrice,2),currency,source_version:"P2-v1",confidence:1
  };
}

export function runP3({productId,transactions,minObservations=6,minDistinctPrices=3}){
  const valid=(transactions||[]).map(x=>({price:Number(x.unit_price??x.price),qty:Number(x.qty??x.quantity)})).filter(x=>x.price>0&&x.qty>0);
  const distinct=new Set(valid.map(x=>x.price.toFixed(2))).size;
  if(valid.length<minObservations||distinct<minDistinctPrices){
    return {product_id:productId,status:"INSUFFICIENT_DATA",elasticity:null,r_squared:null,observation_count:valid.length,distinct_price_count:distinct,confidence:.15,source_version:"P3-v1"};
  }
  const xs=valid.map(x=>Math.log(x.price)), ys=valid.map(x=>Math.log(x.qty));
  const {slope,r2}=linreg(xs,ys);
  if(!Number.isFinite(slope)||slope>=0){
    return {product_id:productId,status:"UNRELIABLE",elasticity:null,r_squared:round(r2,4),observation_count:valid.length,distinct_price_count:distinct,confidence:.2,source_version:"P3-v1"};
  }
  const elasticity=Math.max(-5,slope);
  const confidence=clamp(.45+.35*r2+.02*Math.min(valid.length-6,10),.45,.95);
  return {product_id:productId,status:"ESTIMATED",elasticity:round(elasticity,4),r_squared:round(r2,4),observation_count:valid.length,distinct_price_count:distinct,confidence:round(confidence,4),source_version:"P3-v1"};
}

export function runP4({productId,currentPrice,stockRisk,demandForecast,allowedRange,maxMarkdownPct=.20}){
  if(!allowedRange||allowedRange.status!=="OK") return {product_id:productId,current_price:currentPrice,candidate_price:currentPrice,discount_pct:0,actionable:false,reason:"Missing valid P2 margin floor.",source_version:"P4-v1",confidence:0};
  if(!stockRisk) return {product_id:productId,current_price:currentPrice,candidate_price:currentPrice,discount_pct:0,actionable:false,reason:"No I4 slow-stock/expiry signal.",source_version:"P4-v1",confidence:.4};
  const risk=String(stockRisk.risk_type||"");
  const severity=String(stockRisk.severity||"LOW");
  let discount=0;
  if(risk==="DEAD_STOCK") discount=severity==="HIGH"?.15:.08;
  else if(risk==="EXCESS_STOCK") discount=severity==="HIGH"?.10:.05;
  else if(risk==="EXPIRY_RISK") discount=severity==="HIGH"?.12:.06;
  discount=Math.min(discount,maxMarkdownPct);
  if(discount<=0) return {product_id:productId,current_price:currentPrice,candidate_price:currentPrice,discount_pct:0,actionable:false,reason:"I4 signal does not justify a markdown.",source_version:"P4-v1",confidence:.5};

  // Strong short-term demand reduces, rather than increases, a markdown. It never creates event surge pricing.
  const available=Number(stockRisk.available_stock??0);
  const expected=Number(demandForecast?.expected_qty??0);
  if(available>0&&expected/available>1.5) discount*=.5;

  const unconstrained=Number(currentPrice)*(1-discount);
  const candidate=Math.max(unconstrained,Number(allowedRange.minimum_price));
  const actualDiscount=Math.max(0,1-candidate/Number(currentPrice));
  const actionable=actualDiscount>=.01;
  return {
    product_id:productId,current_price:round(currentPrice),candidate_price:round(candidate),discount_pct:round(actualDiscount,4),actionable,
    reason:actionable?`${risk}/${severity} supports a bounded markdown without crossing the margin floor.`:"Margin floor leaves no meaningful markdown room.",
    source_version:"P4-v1",confidence:round(Math.min(.9,Number(stockRisk.confidence??.7)),2)
  };
}

export function runP5({product,currentInventory,stockRisk,demandForecast,p1,p2,p3,p4,policy}){
  const missing=[];
  if(!p1||p1.status!=="OK")missing.push("P1");
  if(!p2||p2.status!=="OK")missing.push("P2");
  if(!p3||p3.status!=="ESTIMATED")missing.push("P3");
  if(!p4)missing.push("P4");
  if(missing.length){
    return {product_id:product.product_id,current_price:Number(product.current_price),proposed_price:Number(product.current_price),margin_after_pct:null,fairness_checks:["insufficient_evidence"],actionable:false,status:"DRAFT",missing_dependencies:missing,reason:`Missing reliable pricing evidence: ${missing.join(", ")}.`,source_version:"P5-v1",confidence:0};
  }

  const current=Number(product.current_price);
  let proposed=p4.actionable?Number(p4.candidate_price):current;
  const checks=[];
  const maxChange=Number(policy.maximumSinglePriceChangePct??.15);
  const lowerBound=current*(1-maxChange), upperBound=current*(1+maxChange);
  proposed=Math.max(lowerBound,Math.min(upperBound,proposed));
  checks.push("bounded_single_change");

  proposed=Math.max(proposed,Number(p2.minimum_price));
  checks.push("margin_floor_respected");

  const hasEventDriver=(demandForecast.drivers||[]).some(x=>/event|festival|shortage|emergency/i.test(String(x)));
  if(hasEventDriver&&proposed>current&&policy.eventBasedPriceIncreaseAllowed===false){
    proposed=current;
    checks.push("event_surge_blocked");
  } else checks.push("no_event_surge");

  checks.push("no_customer_specific_pricing");
  checks.push("human_approval_required");

  const cost=Number(p2.effective_unit_cost);
  const margin=proposed>0?(proposed-cost)/proposed:0;
  const changePct=current?((proposed-current)/current):0;
  const actionable=Math.abs(changePct)>=.005;
  const confidence=Math.min(Number(p1.confidence??.5),Number(p3.confidence??.5),Number(p4.confidence??.5),Number(demandForecast.confidence??.5));
  const risk=Math.abs(changePct)>.10?"HIGH":"MEDIUM";
  return {
    product_id:product.product_id,current_price:round(current),proposed_price:round(proposed),change_pct:round(changePct,4),
    margin_after_pct:round(margin,4),market_average:p1.market_average,elasticity:p3.elasticity,
    inventory_context:{available_stock:Number(currentInventory.available_stock??currentInventory.available??0),stock_risk:stockRisk?.risk_type??null},
    demand_context:{expected_qty:Number(demandForecast.expected_qty),horizon_days:Number(demandForecast.horizon_days)},
    fairness_checks:checks,actionable,status:actionable?"READY_FOR_REVIEW":"NO_CHANGE",risk_level:risk,
    reason:actionable?"Canonical pricing evidence supports a bounded price change; human approval is required.":"No meaningful safe price change is currently justified.",
    source_version:"P5-v1",confidence:round(confidence,4)
  };
}

export function runPricingDomain({product,competitorObservations,transactions,d4,i1,i4,policy,now=new Date()}){
  const p1=runP1({productId:product.product_id,currentPrice:product.current_price,observations:competitorObservations,now,maxAgeHours:policy.competitorObservationMaxAgeHours});
  const p2=runP2({productId:product.product_id,unitCost:product.unit_cost,marginFloorPct:product.margin_floor_pct,variableFeesPerUnit:product.variable_fees_per_unit||0,currency:product.currency||"ZAR"});
  const p3=runP3({productId:product.product_id,transactions,minObservations:policy.minimumElasticityObservations,minDistinctPrices:policy.minimumDistinctElasticityPrices});
  const p4=runP4({productId:product.product_id,currentPrice:product.current_price,stockRisk:i4,demandForecast:d4,allowedRange:p2,maxMarkdownPct:policy.maximumMarkdownPct});
  const p5=runP5({product,currentInventory:i1,stockRisk:i4,demandForecast:d4,p1,p2,p3,p4,policy});
  return {p1,p2,p3,p4,p5};
}
