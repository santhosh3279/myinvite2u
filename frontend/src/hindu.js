import { createApp } from 'vue'
import HinduWeddingInvite from './pages/hinduweddinginvite.vue'
import './style.css'

const root = document.getElementById('hindu-invitation')
createApp(HinduWeddingInvite, JSON.parse(root.dataset.invitation)).mount(root)
