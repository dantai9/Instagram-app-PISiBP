// ═══════════════════════════════════════════
//  api.js — Gramo API client
// ═══════════════════════════════════════════

const API_USER = 'http://localhost:5000';
const API_POST = 'http://localhost:5001';
const API_FEED = 'http://localhost:5002';

function getToken() {
  return localStorage.getItem('token');
}

function getCurrentUserId() {
  return parseInt(localStorage.getItem('user_id'));
}

function requireAuth() {
  if (!getToken()) window.location.href = 'index.html';
}

function authHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${getToken()}`, ...extra };
}

async function apiFetch(url, options = {}) {
  options.headers = { ...authHeaders(), ...(options.headers || {}) };
  const res = await fetch(url, options);
  if (res.status === 401) {
    localStorage.clear();
    window.location.href = 'index.html';
    return;
  }
  return res;
}

async function apiJson(url, options = {}) {
  options.headers = {
    ...authHeaders({'Content-Type': 'application/json'}),
    ...(options.headers || {})
  };
  const res = await fetch(url, options);
  if (res.status === 401) {
    localStorage.clear();
    window.location.href = 'index.html';
    return;
  }
  const data = await res.json();
  return { ok: res.ok, status: res.status, data };
}

// ── User API ──────────────────────────────

async function getProfile(userId) {
  return apiJson(`${API_USER}/profile/${userId}`);
}

async function updateProfile(formData) {
  return apiFetch(`${API_USER}/profile`, { method: 'PUT', body: formData });
}

async function followUser(userId) {
  return apiJson(`${API_USER}/follow/${userId}`, { method: 'POST' });
}

async function unfollowUser(userId) {
  return apiJson(`${API_USER}/unfollow/${userId}`, { method: 'POST' });
}

async function removeFollower(userId) {
  return apiJson(`${API_USER}/remove-follower/${userId}`, { method: 'POST' });
}

async function blockUser(userId) {
  return apiJson(`${API_USER}/block/${userId}`, { method: 'POST' });
}

async function unblockUser(userId) {
  return apiJson(`${API_USER}/unblock/${userId}`, { method: 'POST' });
}

async function searchUsers(q) {
  return apiJson(`${API_USER}/search?q=${encodeURIComponent(q)}`);
}

async function getFollowRequests() {
  return apiJson(`${API_USER}/follow-requests`);
}

async function acceptFollowRequest(reqId) {
  return apiJson(`${API_USER}/follow-requests/${reqId}/accept`, { method: 'POST' });
}

async function rejectFollowRequest(reqId) {
  return apiJson(`${API_USER}/follow-requests/${reqId}/reject`, { method: 'POST' });
}

// ── Post API ──────────────────────────────

async function getFeed(page = 1) {
  return apiJson(`${API_FEED}/feed?page=${page}&per_page=10`);
}

async function getUserPosts(userId) {
  return apiJson(`${API_POST}/user_posts/${userId}`);
}

async function getPost(postId) {
  return apiJson(`${API_POST}/posts/${postId}`);
}

async function createPost(formData) {
  return apiFetch(`${API_POST}/posts`, { method: 'POST', body: formData });
}

async function updatePostDesc(postId, description) {
  return apiJson(`${API_POST}/posts/${postId}`, {
    method: 'PUT',
    body: JSON.stringify({ description })
  });
}

async function deletePost(postId) {
  return apiJson(`${API_POST}/posts/${postId}`, { method: 'DELETE' });
}

async function deleteFile(postId, fileId) {
  return apiJson(`${API_POST}/posts/${postId}/files/${fileId}`, { method: 'DELETE' });
}

async function likePost(postId) {
  return apiJson(`${API_POST}/posts/${postId}/like`, { method: 'POST' });
}

async function addComment(postId, text) {
  return apiJson(`${API_POST}/posts/${postId}/comment`, {
    method: 'POST', body: JSON.stringify({ text })
  });
}

async function editComment(commentId, text) {
  return apiJson(`${API_POST}/comments/${commentId}`, {
    method: 'PUT', body: JSON.stringify({ text })
  });
}

async function deleteComment(commentId) {
  return apiJson(`${API_POST}/comments/${commentId}`, { method: 'DELETE' });
}

// ── Helpers ───────────────────────────────

function avatarHTML(user, size = 36) {
  if (user && user.profile_picture) {
    return `<img class="avatar" src="${API_USER}/uploads/${user.profile_picture}" width="${size}" height="${size}" alt=""/>`;
  }
  const initials = user ? (user.name || user.username || '?')[0].toUpperCase() : '?';
  return `<div class="avatar-placeholder" style="width:${size}px;height:${size}px;font-size:${Math.round(size*0.4)}px">${initials}</div>`;
}

function timeAgo(isoString) {
  const diff = (Date.now() - new Date(isoString)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

function logout() {
  localStorage.clear();
  window.location.href = 'index.html';
}

// ── Nav search ────────────────────────────

function initNavSearch() {
  const input = document.getElementById('navSearch');
  const results = document.getElementById('searchResults');
  if (!input || !results) return;

  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) { results.classList.remove('open'); return; }
    timer = setTimeout(async () => {
      const r = await searchUsers(q);
      if (!r || !r.ok) return;
      results.innerHTML = r.data.users.length === 0
        ? `<div style="padding:1rem;color:var(--muted);font-size:0.85rem">No results</div>`
        : r.data.users.map(u => `
            <a class="search-item" href="profile.html?id=${u.id}">
              ${avatarHTML(u, 32)}
              <div>
                <div style="font-size:0.875rem;font-weight:500">${u.name}</div>
                <div style="font-size:0.75rem;color:var(--muted)">@${u.username}</div>
              </div>
            </a>`).join('');
      results.classList.add('open');
    }, 280);
  });

  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !results.contains(e.target))
      results.classList.remove('open');
  });
}
