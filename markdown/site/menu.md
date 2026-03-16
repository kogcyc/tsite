---
title: m e n u
desc:  
image:
template: template_menu.html
exclude:
  - search
  - all_pages
---
###About Us###
Kogswell Cycles is a convergence of ideas about bicycle use.
Our aim is to create a place where people who care about making bicycles safer, more comfortable, more durable, and more affordable can share ideas and learn from one another.
Anyone serious about that goal is welcome here.

###Contact Us###
Call or text us during regular office hours in California where it is currently <span id="ca-clock" style="font-weight:700;color:#a00">--:--</span>.

Or email us: m@kogswellcycles.com

<script>
(function () {
  const el = document.getElementById("ca-clock");

  function updateClock() {
    const now = new Date();
    const time = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true
    }).format(now);

    el.textContent = time.toLowerCase(); // makes AM/PM -> am/pm
  }

  updateClock();
  setInterval(updateClock, 1000);
})();
</script>