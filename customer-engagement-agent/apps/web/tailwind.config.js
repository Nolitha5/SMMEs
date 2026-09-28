/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      boxShadow: { soft: '0 18px 50px rgba(0,0,0,.18)' }
    }
  },
  plugins: []
};
