// --- Admin & Hiring General ---
function switchTab(name, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

// --- Recommendations ---
function filterCards(type, btn) {
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.rec-card').forEach(card => {
    const sc = +card.dataset.score, applied = card.dataset.applied === 'true';
    const show = type === 'all' || (type === 'strong' && sc >= 70) || (type === 'good' && sc >= 40 && sc < 70)
      || (type === 'applied' && applied) || (type === 'notapplied' && !applied);
    card.style.display = show ? 'flex' : 'none';
  });
}

// --- Login Form ---
const roleInfo = {
  candidate: '💡 Candidate: Create profile & apply for jobs',
  hiring: '💼 Hiring Team: Review applications & manage job roles',
  admin: '⚙ Admin: System maintenance & user management'
};

function setRole(role, btn) {
  document.querySelectorAll('.role-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  
  if (document.getElementById('roleInput')) {
    document.getElementById('roleInput').value = role;
  }
  
  if (document.getElementById('roleInfo')) {
    document.getElementById('roleInfo').textContent = roleInfo[role];
  }
}

// --- Hiring Dashboard ---
function filterApps(jobId, btn) {
  document.querySelectorAll('.filter-chip').forEach(c => {
    c.style.background = 'var(--white)';
    c.style.color = 'var(--text2)';
    c.style.borderColor = 'var(--border)';
  });
  
  btn.style.background = 'var(--accent)';
  btn.style.color = '#fff';
  btn.style.borderColor = 'var(--accent)';
  
  document.querySelectorAll('#appsList .app-card').forEach(card => {
    card.style.display = (jobId === 'all' || card.dataset.jobid == jobId) ? 'block' : 'none';
  });
}

// --- Candidate Form ---
let currentFormStep = 1;
const totalFormSteps = 5;
const formProgress = [20, 40, 60, 80, 100];

function changeStep(dir) {
  const panels = document.querySelectorAll('.step-panel');
  if (panels.length === 0) return;
  
  const required = panels[currentFormStep - 1].querySelectorAll('[required]');
  
  if (dir === 1) {
    for (let el of required) {
      if (!el.value.trim()) {
        el.focus();
        el.style.borderColor = 'var(--red)';
        setTimeout(() => el.style.borderColor = '', 2000);
        return;
      }
    }
  }
  
  document.getElementById('si-' + currentFormStep).classList.remove('active');
  
  if (dir === 1) document.getElementById('si-' + currentFormStep).classList.add('done');
  if (dir === 1 && currentFormStep > 1) document.getElementById('sl-' + (currentFormStep - 1)).classList.add('done');
  
  currentFormStep += dir;
  
  document.getElementById('si-' + currentFormStep).classList.add('active');
  if (dir === -1) { document.getElementById('si-' + (currentFormStep + 1)).classList.remove('done', 'active'); }
  
  panels.forEach((p, i) => p.classList.toggle('active', i === currentFormStep - 1));
  
  document.getElementById('progressBar').style.width = formProgress[currentFormStep - 1] + '%';
  document.getElementById('stepCount').textContent = 'Step ' + currentFormStep + ' of ' + totalFormSteps;
  
  document.getElementById('prevBtn').style.display = currentFormStep === 1 ? 'none' : 'inline-flex';
  document.getElementById('nextBtn').style.display = currentFormStep === totalFormSteps ? 'none' : 'inline-flex';
  document.getElementById('submitBtn').style.display = currentFormStep === totalFormSteps ? 'inline-flex' : 'none';
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
