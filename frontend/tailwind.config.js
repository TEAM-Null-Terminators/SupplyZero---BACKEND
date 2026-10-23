/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: { colors: { ink: '#14241f', muted: '#718078', line: '#e4ebe7', canvas: '#f5f8f6', brand: '#156b52' }, boxShadow: { panel: '0 10px 35px rgba(23,45,36,.055)' } } },
  plugins: [],
}
