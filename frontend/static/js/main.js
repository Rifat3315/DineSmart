// Cart badge is now rendered server-side via {{ cart_count }} in base.html
// (kept as a no-op so old inline calls elsewhere don't break)
function updateCartCount(){}


// ===== Chatbot widget =====
document.addEventListener('DOMContentLoaded', ()=>{
  const fab = document.getElementById('chatFab');
  const panel = document.getElementById('chatPanel');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');
  const body = document.getElementById('chatBody');

  if(fab){
    fab.addEventListener('click', ()=> panel.classList.toggle('open'));
  }

  if(form){
    form.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const text = input.value.trim();
      if(!text) return;

      appendMsg(text, 'user');
      input.value = '';

      const thinkingMsg = appendMsg('...', 'bot');

      try{
        const res = await fetch('/chatbot/ask/', {
          method: 'POST',
          headers: {'Content-Type':'application/json', 'X-CSRFToken': getCookie('csrftoken')},
          body: JSON.stringify({message: text})
        });
        const data = await res.json();
        thinkingMsg.textContent = data.reply;
      }catch(err){
        thinkingMsg.textContent = "Sorry, I couldn't reach the AI assistant. Please try again.";
      }
    });
  }

  function appendMsg(text, who){
    const div = document.createElement('div');
    div.className = `chat-msg ${who}`;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  }
});

function getCookie(name){
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if(parts.length === 2) return parts.pop().split(';').shift();
}
