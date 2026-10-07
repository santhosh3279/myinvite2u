import { createRouter, createWebHashHistory } from 'vue-router'

// Hash routes work under Frappe's /invite page without proxy rewrites.
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: () => import('./pages/Home.vue') },
    { path: '/hinduweddinginvite', component: () => import('./pages/hinduweddinginvite.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
