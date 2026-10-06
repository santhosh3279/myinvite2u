<script setup>
import { FrappeUIProvider } from 'frappe-ui'
</script>

<template>
  <FrappeUIProvider>
    <main class="invite-home">
      <header><a href="/invite">Invitation <span>♡</span></a><a href="/app">Open Desk ↗</a></header>
      <section class="welcome">
        <p class="kicker">A celebration starts with an invitation</p>
        <h1>Your story.<br><em>Your forever.</em></h1>
        <p class="intro">Create a wedding invitation that brings every detail together.<br>One beautiful page, made for your favourite people.</p>
        <a class="primary-link" href="/app/wedding-invitation/new">Create an invitation <span>↗</span></a>
      </section>
      <section class="home-cards">
        <a href="/app/wedding-invitation"><span class="kicker">01 / Create & publish</span><h2>Wedding invitations</h2><p>Add your names, date, venues, story and photos. Publish your page and share its personal address.</p><span class="card-link">Manage invitations ↗</span></a>
        <a href="/app/wedding-rsvp"><span class="kicker">02 / Celebrate together</span><h2>Your guest responses</h2><p>See who’s joining you, their party sizes, dietary requirements and messages, all in one place.</p><span class="card-link">View RSVPs ↗</span></a>
      </section>
      <p class="home-note">Sign in with a System Manager account to manage invitations.<br>Your guests can open published invitation pages without signing in.</p>
    </main>
  </FrappeUIProvider>
</template>

<style scoped>
.invite-home{min-height:100vh;background:#faf7f0;color:#403a35;font-family:Arial,sans-serif;padding:0 7% 45px}header{height:90px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dcd1bf}header a{color:inherit;text-decoration:none;font-size:12px}header a:first-child{font:27px Georgia,serif}header span{color:#723d49}.welcome{text-align:center;padding:85px 10px 65px}.kicker{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#82766c}h1{font:clamp(52px,7vw,86px)/1.12 Georgia,serif;letter-spacing:-3px;margin:22px 0}h1 em{color:#723d49;font-weight:400}.intro{font-size:14px;line-height:1.8;color:#82766c}.primary-link{display:inline-flex;gap:35px;background:#723d49;color:#faf7f0;padding:17px 24px;margin-top:30px;text-decoration:none;font-size:12px}.home-cards{display:grid;grid-template-columns:1fr 1fr;gap:24px;max-width:1000px;margin:auto}.home-cards>a{border:1px solid #dcd1bf;padding:34px;text-decoration:none;color:inherit;transition:background .2s}.home-cards>a:hover{background:#f1ebdf}.home-cards h2{font:30px Georgia,serif;margin:20px 0 15px}.home-cards p{font-size:13px;line-height:1.8;color:#82766c}.card-link{display:block;color:#723d49;font-size:12px;margin-top:28px}.home-note{text-align:center;font-size:11px;line-height:1.8;color:#82766c;margin-top:35px}@media(max-width:650px){.welcome{padding-top:60px}.home-cards{grid-template-columns:1fr}.home-cards>a{padding:25px}header{height:75px}h1{letter-spacing:-2px}}
</style>
