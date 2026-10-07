<script setup>
// Adapted from vigneshwarcj03/weddingInvitationWebsite (MIT).
// See invite/public/hindu-wedding/LICENSE and SOURCE.md.
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
  groom: { type: String, default: 'Karthik' },
  bride: { type: String, default: 'Shakti' },
  weddingDate: { type: String, default: '2027-05-16T10:00:00+05:30' },
  receptionDate: { type: String, default: '2027-05-15T19:00:00+05:30' },
  timeZone: { type: String, default: 'Asia/Kolkata' },
  venue: { type: String, default: 'M Weddings & Conventions' },
  city: { type: String, default: 'Chennai, India' },
  // Set to a published Wedding Invitation route when reusing this page.
  invitationRoute: { type: String, default: '' },
})
const route = useRoute()
const guest = computed(() => String(route.query.guest || new URLSearchParams(window.location.search).get('guest') || 'Family & Friends').slice(0, 140))
const asset = (file) => `/assets/invite/hindu-wedding/${encodeURIComponent(file).replaceAll('%2F', '/')}`
const entered = ref(false)
const opening = ref(false)
const audio = ref(null)
const playing = ref(false)
const musicError = ref('')
const hero = ref(null)
const now = ref(Date.now())
let timer, entranceTimer
const dateLabel = (value, withTime = false) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date to be announced'
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: props.timeZone, day: 'numeric', month: 'long', year: 'numeric',
    ...(withTime ? { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' } : { weekday: 'long' }),
  }).format(date)
}
const remaining = computed(() => Math.max(0, Math.floor((new Date(props.weddingDate).getTime() - now.value) / 1000)) || 0)
const countdown = computed(() => [
  ['Days', Math.floor(remaining.value / 86400)], ['Hours', Math.floor(remaining.value / 3600) % 24],
  ['Minutes', Math.floor(remaining.value / 60) % 60], ['Seconds', remaining.value % 60],
])
const stories = computed(() => [
  ['2020', 'Our First Meeting', 'A smile at a family function, the start of a beautiful journey together.'],
  ['2021', 'Growing Closer', 'Shared dreams and laughter made our bond stronger every day.'],
  [String(new Date(props.weddingDate).getFullYear()), 'The Proposal', 'With blessings from our families, we decided on forever.'],
  ['Today', 'Joining Hands', 'With joyful hearts, we celebrate our wedding and new beginnings.'],
])
const celebrations = computed(() => [
  { title: 'Reception Celebrations', events: [
    { image: 'Reception.png', title: 'Reception', text: 'An evening of love, laughter and togetherness.', date: props.receptionDate },
    { image: 'DJ.png', title: 'Live DJ & Dance Floor', text: 'Bring your dancing shoes. Let’s fill the evening with music and memories.' },
    { image: 'Games.png', title: 'Games & Entertainment', text: 'A little friendly competition, plenty of laughter, and something for everyone.' },
    { image: 'Food.png', title: 'A Feast for Everyone', text: 'Celebrate over a delicious Indian dinner, refreshing drinks and sweet treats.' },
  ] },
  { title: 'Wedding Ceremony', events: [
    { image: 'Wedding Ceremony.png', title: 'The Sacred Wedding', text: 'With the blessings of our families, we begin our forever.', date: props.weddingDate },
    { image: 'CoupleGames.png', title: 'Joyful Traditions', text: 'Playful moments and cherished customs bring our two families together.' },
    { image: 'Muhurtham.png', title: 'The Muhurtham', text: 'Sacred vows, a shower of blessings, and a lifetime of love.' },
    { image: 'Feast.png', title: 'Wedding Feast', text: 'Join us for a traditional feast as we celebrate this beautiful new beginning.' },
  ] },
])
const tabs = [ ['engagement', 'Engagement'], ['pre', 'Pre-wedding'], ['fam', 'Family'] ]
const activeTab = ref('engagement')
const selected = ref(0)
const lightbox = ref(null)
const photo = (index) => asset(`${activeTab.value}${index}.jfif`)
const photoLabel = (index) => `${tabs.find(([key]) => key === activeTab.value)[1]} photograph ${index}`
const mapsQuery = computed(() => encodeURIComponent(`${props.venue}, ${props.city}`))
function openPhoto(index) { selected.value = index; lightbox.value.showModal() }
function movePhoto(step) { selected.value = (selected.value - 1 + step + 3) % 3 + 1 }
async function toggleMusic() {
  musicError.value = ''
  if (playing.value) { audio.value.pause(); return }
  try { await audio.value.play() } catch { musicError.value = 'Music could not play. Tap to try again.' }
}
function enter() {
  opening.value = true
  entranceTimer = setTimeout(async () => {
    entered.value = true
    await nextTick()
    hero.value?.focus({ preventScroll: true })
  }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 900)
}
function goTo(id) { document.getElementById(id)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }) }
const form = reactive({ guest_name: '', email: '', attendance: 'Attending', guest_count: 1, message: '', website: '' })
const submitting = ref(false)
const response = ref('')
const submitted = ref(false)
async function submit() {
  if (submitting.value) return
  response.value = ''
  if (!props.invitationRoute) {
    response.value = `Thank you, ${form.guest_name}! This is a template preview; your response has not been sent or saved.`
    return
  }
  submitting.value = true
  try {
    const headers = { 'Content-Type': 'application/json' }
    const csrf = window.frappe?.csrf_token || window.csrf_token
    if (csrf) headers['X-Frappe-CSRF-Token'] = csrf
    const result = await fetch('/api/method/invite.api.submit_rsvp', {
      method: 'POST', credentials: 'same-origin', headers,
      body: JSON.stringify({ ...form, route: props.invitationRoute }),
    })
    const body = await result.json()
    if (!result.ok || !body.message?.success) throw new Error('Unable to send your response. Please check your details and try again, or contact the hosts.')
    submitted.value = true
    response.value = `Thank you, ${form.guest_name}. Your response has been received!`
  } catch (error) {
    response.value = error instanceof TypeError ? 'Connection failed. Please try again.' : error.message
  } finally { submitting.value = false }
}
onMounted(() => {
  form.guest_name = guest.value === 'Family & Friends' ? '' : guest.value
  timer = setInterval(() => { now.value = Date.now() }, 1000)
})
onUnmounted(() => { clearInterval(timer); clearTimeout(entranceTimer); audio.value?.pause() })
</script>

<template>
  <div class="hindu-invite">
    <audio ref="audio" :src="asset('music/wedding-theme.mp3')" loop preload="none" @play="playing = true" @pause="playing = false" />
    <div v-if="!entered" class="entrance" :class="{ opening }" :style="{ backgroundImage: `url(${asset('Background_Temple_image.png')})` }">
      <img class="door left" :src="asset('temple_door_left.png')" alt="" />
      <img class="door right" :src="asset('temple_door_right.png')" alt="" />
      <section class="welcome-card">
        <p class="eyebrow">With love & blessings</p>
        <h1>You Are Invited</h1>
        <span class="ornament" aria-hidden="true">✦</span>
        <p>Dear {{ guest }},</p>
        <img class="welcome-couple" :src="asset('Couples_1.jpg')" alt="The happy couple" />
        <h2>{{ groom }} <i>&</i> {{ bride }}</h2>
        <p>Two hearts. Two families. One beautiful beginning.</p>
        <button class="gold-button" :disabled="opening" @click="enter">{{ opening ? 'Opening…' : 'Enter Invitation' }} <span aria-hidden="true">→</span></button>
        <p class="small">We can’t wait to celebrate with you.</p>
      </section>
    </div>

    <main v-if="entered">
      <nav class="invitation-nav" aria-label="Invitation sections">
        <RouterLink to="/" aria-label="Back to invitation home">♡</RouterLink>
        <button @click="goTo('celebrations')">Celebrations</button>
        <button @click="goTo('gallery')">Gallery</button>
        <button @click="goTo('rsvp')">RSVP</button>
      </nav>
      <header class="hero">
        <img class="hero-flowers" :src="asset('TopHero.png')" alt="" />
        <div class="petals" aria-hidden="true"><img v-for="i in 10" :key="i" :src="asset('rose-petal.png')" alt="" :style="{ left: `${i * 9}%`, animationDelay: `${i * -1.7}s`, animationDuration: `${10 + i}s` }" /></div>
        <img class="hero-couple" :src="asset('HeroSection_Image.png')" alt="Illustration of a couple on a flower-adorned swing" />
        <p class="eyebrow">Together with their families</p>
        <h1 ref="hero" tabindex="-1">{{ groom }} <span>&</span> {{ bride }}</h1>
        <img class="name-ornament" :src="asset('heroCenter.png')" alt="" />
        <p class="hero-text">Invite you to celebrate their wedding<br>and the beginning of their forever.</p>
        <p class="wedding-date">{{ dateLabel(weddingDate) }}</p>
        <p>{{ city }}</p>
        <button class="text-button" @click="goTo('story')">Our story <span aria-hidden="true">↓</span></button>
        <img class="hero-bottom" :src="asset('bottom.png')" alt="" />
      </header>

      <section id="story" class="section story">
        <p class="eyebrow">Every love has a story</p><h2>Ours is our favourite</h2><div class="ornament" aria-hidden="true">✦</div>
        <div class="timeline">
          <article v-for="([year, title, text], index) in stories" :key="title" class="story-row">
            <img :src="asset(`Story${index + 1}.png`)" :alt="title" loading="lazy" />
            <div class="story-card"><p class="eyebrow">{{ year }}</p><h3>{{ title }}</h3><p>{{ text }}</p></div>
          </article>
        </div>
      </section>

      <section class="section countdown-section">
        <p class="eyebrow">A lifetime of togetherness awaits</p><h2>The Wedding</h2><div class="ornament" aria-hidden="true">✦</div>
        <p>{{ dateLabel(weddingDate, true) }}</p>
        <div class="countdown" role="timer" aria-label="Time until the wedding"><div v-for="[label, value] in countdown" :key="label"><strong>{{ String(value).padStart(2, '0') }}</strong><span>{{ label }}</span></div></div>
        <p>{{ remaining ? 'Counting the moments until we celebrate with you.' : 'Here’s to love, laughter and happily ever after.' }}</p>
      </section>

      <div id="celebrations">
        <section v-for="group in celebrations" :key="group.title" class="section celebrations">
          <p class="eyebrow">You’re part of our celebration</p><h2>{{ group.title }}</h2><div class="ornament" aria-hidden="true">✦</div>
          <div class="event-grid">
            <article v-for="event in group.events" :key="event.title" class="event">
              <img :src="asset(event.image)" :alt="event.title" loading="lazy" />
              <div class="event-card"><h3>{{ event.title }}</h3><p>{{ event.text }}</p><template v-if="event.date"><p class="event-detail">{{ dateLabel(event.date, true) }}</p><p class="event-detail">{{ venue }}<br>{{ city }}</p></template></div>
            </article>
          </div>
        </section>
      </div>

      <section class="section location">
        <p class="eyebrow">Meet us here</p><h2>A place for beautiful memories</h2><div class="ornament" aria-hidden="true">✦</div>
        <h3>{{ venue }}</h3><p>{{ city }}</p>
        <iframe :src="`https://maps.google.com/maps?q=${mapsQuery}&output=embed`" title="Wedding venue map" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen />
        <a class="gold-button" :href="`https://www.google.com/maps/search/?api=1&query=${mapsQuery}`" target="_blank" rel="noopener noreferrer">Get directions ↗</a>
      </section>

      <section id="gallery" class="section gallery">
        <p class="eyebrow">Little moments, lasting memories</p><h2>Our Wedding Gallery</h2><div class="ornament" aria-hidden="true">✦</div>
        <div class="gallery-tabs" aria-label="Photo categories"><button v-for="[key, label] in tabs" :key="key" :aria-pressed="activeTab === key" @click="activeTab = key">{{ label }}</button></div>
        <div class="gallery-grid"><button v-for="index in 3" :key="`${activeTab}${index}`" :aria-label="`Enlarge ${photoLabel(index)}`" @click="openPhoto(index)"><img :src="photo(index)" :alt="photoLabel(index)" loading="lazy" /><span>View photograph ↗</span></button></div>
        <dialog ref="lightbox" class="lightbox" aria-label="Wedding photographs" @click="($event.target === lightbox) && lightbox.close()" @keydown.left.prevent="movePhoto(-1)" @keydown.right.prevent="movePhoto(1)">
          <div class="lightbox-content"><button class="close-photo" autofocus aria-label="Close photograph" @click="lightbox.close()">×</button><img v-if="selected" :src="photo(selected)" :alt="photoLabel(selected)" /><div class="photo-controls"><button aria-label="Previous photograph" @click="movePhoto(-1)">←</button><span>{{ selected }} / 3</span><button aria-label="Next photograph" @click="movePhoto(1)">→</button></div></div>
        </dialog>
      </section>

      <section id="rsvp" class="section rsvp">
        <p class="eyebrow">Your presence is our greatest gift</p><h2>Join our celebration</h2><div class="ornament" aria-hidden="true">✦</div>
        <p>Share your wishes and blessings.</p>
        <p v-if="!invitationRoute" class="preview-note">Template preview · Responses are not sent or saved.</p>
        <form v-if="!submitted" @submit.prevent="submit">
          <label>Your name<input v-model="form.guest_name" autocomplete="name" required maxlength="140" placeholder="Your full name" /></label>
          <label>Email<input v-model="form.email" type="email" autocomplete="email" required maxlength="140" placeholder="you@example.com" /></label>
          <label>Will you join us?<select v-model="form.attendance"><option>Attending</option><option>Not Attending</option></select></label>
          <label v-if="form.attendance === 'Attending'">Number of guests<input v-model.number="form.guest_count" type="number" min="1" required /></label>
          <label>Your wishes<textarea v-model="form.message" rows="4" maxlength="2000" placeholder="A little love for the happy couple…" /></label>
          <div class="honeypot" aria-hidden="true"><label>Leave empty<input v-model="form.website" tabindex="-1" autocomplete="off" /></label></div>
          <button class="gold-button" :disabled="submitting">{{ submitting ? 'Sending…' : invitationRoute ? 'Send RSVP' : 'Preview RSVP' }}</button>
        </form>
        <p v-if="response" class="response" role="status">{{ response }}</p>
      </section>
      <footer><span aria-hidden="true">♡</span><h2>{{ groom }} & {{ bride }}</h2><p>Thank you for being part of our forever.</p><p class="small">With love, our families</p><RouterLink to="/">Explore invitations ↗</RouterLink></footer>
      <div class="music-control"><span v-if="musicError" role="status">{{ musicError }}</span><button :aria-pressed="playing" :aria-label="playing ? 'Pause music' : 'Play music'" @click="toggleMusic">{{ playing ? '♫ Pause' : '♫ Music' }}</button></div>
    </main>
  </div>
</template>

<style scoped>
.hindu-invite{--gold:#b38a2e;--wine:#660033;--cream:#faf5e9;min-height:100vh;background:var(--cream);background-image:radial-gradient(#b38a2e18 .8px,transparent .8px);background-size:25px 25px;color:#56432f;font:16px/1.7 Georgia,'Times New Roman',serif;overflow-x:clip}
.hindu-invite *{box-sizing:border-box}.hindu-invite button,.hindu-invite a,.hindu-invite input,.hindu-invite select,.hindu-invite textarea{-webkit-tap-highlight-color:transparent}.hindu-invite button{cursor:pointer;font:inherit}.hindu-invite button:disabled{cursor:wait;opacity:.7}.hindu-invite :focus-visible{outline:3px solid #c28632;outline-offset:5px}.hindu-invite h1,.hindu-invite h2,.hindu-invite h3{font-family:Georgia,'Times New Roman',serif;font-weight:400;line-height:1.2}.hindu-invite h2{font-size:clamp(30px,4vw,46px);color:var(--wine);margin:10px 0 20px}.hindu-invite h3{font-size:26px;margin:0 0 14px}.hindu-invite p{margin:12px 0}.eyebrow{font:11px/1.7 Arial,sans-serif!important;letter-spacing:3px;text-transform:uppercase;color:#8a671e}.small{font-size:12px!important}.ornament{display:flex;align-items:center;justify-content:center;gap:18px;color:var(--gold);margin:20px auto 35px}.ornament:before,.ornament:after{content:'';width:65px;height:1px;background:linear-gradient(90deg,transparent,var(--gold))}.ornament:after{transform:rotate(180deg)}.gold-button{display:inline-flex;justify-content:center;align-items:center;gap:24px;padding:13px 25px;background:linear-gradient(120deg,#e6c673,#d4af37);color:#422811;border:1px solid #a78025;border-radius:6px;text-decoration:none;font:14px/1.6 Arial,sans-serif!important;box-shadow:0 6px 20px #8a671e20}.gold-button:hover{filter:brightness(1.06)}
.entrance{min-height:100svh;display:grid;place-items:center;padding:28px 20px;background-position:center;background-size:cover;position:relative;isolation:isolate;overflow:hidden}.entrance:before{content:'';position:absolute;inset:0;background:#22120944;z-index:-1}.door{position:absolute;top:0;height:100%;width:50%;object-fit:fill;z-index:-1;transition:transform .9s ease-in-out}.left{left:0}.right{right:0}.opening .left{transform:translateX(-100%)}.opening .right{transform:translateX(100%)}.welcome-card{width:min(100%,460px);padding:32px 25px;background:#fff8e7f5;border:1px solid #d4af37;outline:1px solid #d4af3780;outline-offset:8px;border-radius:120px 120px 12px 12px;text-align:center;box-shadow:0 20px 80px #190a0860;transition:opacity .7s,transform .9s}.opening .welcome-card{opacity:0;transform:scale(.94)}.welcome-card h1{font-size:clamp(30px,5vw,40px);color:var(--wine);margin:12px 0}.welcome-card h2{font-size:29px}.welcome-card i{color:var(--gold)}.welcome-card .ornament{margin:12px auto}.welcome-card p{font-size:14px}.welcome-couple{width:130px;height:145px;object-fit:cover;border-radius:70px 70px 10px 10px;border:2px solid #d4af37;margin:12px auto;display:block}.welcome-card .gold-button{margin-top:14px}
.invitation-nav{display:flex;justify-content:center;align-items:center;gap:28px;padding:13px 20px;border-bottom:1px solid #b38a2e30;background:#fff9ed;position:relative;z-index:2}.invitation-nav a,.invitation-nav button{color:var(--wine);text-decoration:none;background:none;border:0;font-size:13px}.invitation-nav a{font-size:26px}.hero{position:relative;text-align:center;padding:0 24px 100px;isolation:isolate;overflow:hidden}.hero-flowers{position:absolute;top:0;left:0;width:100%;height:190px;object-fit:cover;object-position:top;z-index:-1;pointer-events:none}.hero-couple{display:block;height:380px;max-width:90%;object-fit:contain;margin:0 auto 22px;transform-origin:top center;animation:sway 7s ease-in-out infinite}.hero h1{font-size:clamp(48px,8vw,88px);color:#963d53;margin:17px auto;letter-spacing:-2px}.hero h1 span{font-style:italic;color:var(--gold);font-size:.7em}.name-ornament{width:180px;height:45px;object-fit:contain;margin:0 auto}.hero-text{font-size:19px;line-height:1.8}.wedding-date{font-size:16px;letter-spacing:1px;color:var(--wine);padding-top:12px}.text-button{border:0;background:transparent;color:#896b2d;margin-top:20px;font-size:13px!important}.text-button span{display:block;font-size:24px}.hero-bottom{position:absolute;bottom:0;left:0;width:100%;height:75px;object-fit:cover;object-position:top;z-index:-1}.petals{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:-1}.petals img{position:absolute;top:-35px;width:18px;animation:fall linear infinite;opacity:.7}
.section{max-width:1120px;margin:0 auto;padding:90px 30px;text-align:center;scroll-margin-top:25px}.story{max-width:940px}.timeline{position:relative;margin-top:55px}.timeline:before{content:'';position:absolute;top:0;bottom:0;left:50%;width:1px;background:#d4af3780}.story-row{display:grid;grid-template-columns:1fr 1fr;align-items:center;gap:80px;margin:0 0 65px;position:relative}.story-row:before{content:'';position:absolute;left:calc(50% - 5px);top:50%;width:11px;height:11px;border-radius:50%;background:var(--gold);box-shadow:0 0 0 7px var(--cream)}.story-row>img{width:100%;height:320px;object-fit:cover;border-radius:130px 130px 12px 12px;border:1px solid #d4af3740;box-shadow:0 10px 30px #6c482b16}.story-card{background:#fffaf0;border:1px solid #dac8a1;padding:32px;text-align:left;border-radius:12px;box-shadow:0 8px 25px #6c482b0b}.story-card h3{color:var(--wine)}.story-row:nth-child(even)>img{grid-column:2;grid-row:1}.story-row:nth-child(even) .story-card{grid-column:1;grid-row:1}.countdown-section{border-block:1px solid #d4af3740;max-width:100%;background:#f3ead8}.countdown{display:flex;justify-content:center;gap:30px;margin:45px 0}.countdown>div{display:flex;flex-direction:column;align-items:center;gap:14px}.countdown strong{display:grid;place-items:center;width:94px;height:94px;border-radius:50%;border:2px solid #d4af37;background:var(--wine);color:#fff9e9;font-size:30px;font-weight:400;box-shadow:0 8px 25px #66003318}.countdown span{font:10px Arial,sans-serif;letter-spacing:2px;text-transform:uppercase;color:#83601c}
.event-grid{display:grid;grid-template-columns:1fr 1fr;gap:55px 38px;margin:45px auto 0;max-width:850px}.event>img{width:100%;height:310px;object-fit:contain;display:block;margin:auto auto 18px}.event-card{border:1px solid #d4af37;border-radius:16px;background:var(--wine);color:#fff5dd;padding:30px;box-shadow:0 10px 30px #66003312;min-height:220px}.event-card h3{color:#fff5dd}.event-card p{font-size:15px}.event-detail{border:1px solid #d4af3770;background:#ffffff08;border-radius:9px;padding:12px;font-size:13px!important}.location{max-width:940px}.location iframe{width:100%;height:380px;border:1px solid #d4af37;border-radius:16px;margin:25px 0}.gallery-tabs{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-bottom:35px}.gallery-tabs button{border:1px solid #d4af3770;border-radius:30px;padding:9px 22px;background:#fffaf0;font-size:14px}.gallery-tabs button[aria-pressed=true]{background:var(--wine);color:#fff5dd}.gallery-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.gallery-grid button{position:relative;padding:0;overflow:hidden;border:1px solid #dac8a1;border-radius:12px;background:#e8d3a5;text-align:left}.gallery-grid img{width:100%;height:310px;object-fit:cover;transition:transform .4s}.gallery-grid button:hover img{transform:scale(1.04)}.gallery-grid span{position:absolute;bottom:15px;left:12px;border-radius:5px;background:#321521bb;color:white;padding:6px 10px;font:12px Arial,sans-serif}.lightbox{padding:0;border:0;background:transparent;color:#fff;max-width:min(90vw,900px);max-height:94svh;overflow:auto}.lightbox::backdrop{background:#170710ed}.lightbox-content{padding:42px 12px 12px;position:relative}.lightbox img{max-width:100%;height:70svh;object-fit:contain;margin:auto}.lightbox button{border:1px solid #ffffff60;background:#ffffff18;color:#fff;border-radius:5px;min-width:42px;min-height:38px}.close-photo{position:absolute;right:12px;top:0;font-size:25px!important}.photo-controls{display:flex;justify-content:space-between;align-items:center;margin-top:15px}
.rsvp{max-width:620px}.rsvp form{position:relative;display:grid;gap:20px;text-align:left;background:var(--wine);border:1px solid #d4af37;border-radius:16px;color:#fff5dd;padding:35px;margin-top:28px}.rsvp label{display:grid;gap:8px;font-size:14px}.rsvp input,.rsvp textarea,.rsvp select{width:100%;border:1px solid #d4af3777;border-radius:6px;background:#ffffff0a;color:#fff;padding:12px;font:16px/1.5 Arial,sans-serif}.rsvp select option{color:#432733;background:#fff5dd}.rsvp input::placeholder,.rsvp textarea::placeholder{color:#e4c9d7}.rsvp .honeypot{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.preview-note{font:12px/1.6 Arial,sans-serif;color:#765828}.response{border:1px solid #d4af37;border-radius:8px;padding:20px;background:#fff8e7}.hindu-invite footer{text-align:center;padding:60px 24px 100px;border-top:1px solid #d4af3740;background:#f3ead8}.hindu-invite footer>span{font-size:40px;color:var(--gold)}.hindu-invite footer a{color:var(--wine);font-size:12px}.music-control{position:fixed;bottom:20px;right:20px;z-index:4;display:flex;align-items:center;gap:10px}.music-control button{border:1px solid #d4af37;background:var(--wine);color:#fff5dd;border-radius:30px;padding:11px 18px;box-shadow:0 3px 20px #0002;font-size:13px}.music-control>span{max-width:200px;background:#fff8e7;border:1px solid #d4af37;padding:10px;font-size:12px}
@keyframes sway{0%,100%{transform:rotate(-1deg)}50%{transform:rotate(1deg)}}@keyframes fall{to{transform:translate(40px,1000px) rotate(280deg)}}
@media(max-width:640px){.invitation-nav{gap:20px}.hero-couple{height:310px}.hero-flowers{height:115px}.hero h1{max-width:340px}.section{padding:65px 20px}.story-row{gap:20px;grid-template-columns:1fr;margin-bottom:40px}.story-row>img{width:210px;height:260px;margin:auto;position:relative}.story-card{text-align:center;padding:24px;position:relative}.story-row:nth-child(even)>img,.story-row:nth-child(even) .story-card{grid-column:auto;grid-row:auto}.story-row:before{display:none}.countdown{gap:12px}.countdown strong{width:65px;height:65px;font-size:23px}.countdown span{font-size:9px;letter-spacing:1px}.event-grid{grid-template-columns:1fr;gap:38px}.event>img{height:300px}.event-card{min-height:auto;padding:25px}.gallery-grid{grid-template-columns:1fr}.gallery-grid img{height:340px}.location iframe{height:280px}.rsvp form{padding:25px}.welcome-card{padding:25px 18px}.welcome-couple{height:125px;width:115px}}
@media(prefers-reduced-motion:reduce){.hindu-invite *{animation:none!important;transition:none!important}.petals{display:none}}
</style>
