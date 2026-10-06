import preset, { content } from 'frappe-ui/tailwind'

export default {
  presets: [preset],
  content: [...content, './frontend/index.html', './frontend/src/**/*.{vue,js,ts}'],
}
