import type { AgentEvent } from '@cea/shared';

type Listener = (event: AgentEvent) => void;
class TypedEventBus {
  private listeners = new Set<Listener>();
  subscribe(listener: Listener) { this.listeners.add(listener); return () => this.listeners.delete(listener); }
  publish(event: AgentEvent) { this.listeners.forEach(listener => listener(event)); }
}
export const eventBus = new TypedEventBus();
