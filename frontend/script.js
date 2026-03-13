const API = {
  usersBase: () => document.getElementById('userServiceUrl').value.trim(),
  postsBase: () => document.getElementById('postServiceUrl').value.trim(),
  feedBase: () => document.getElementById('feedServiceUrl').value.trim(),

  routes: {
    users: '/users',
    follow: '/follow',
    posts: '/posts',
    feedByUser: (userId) => `/feed/${userId}`,
  },
};

const els = {
  usersList: document.getElementById('usersList'),
  postsList: document.getElementById('postsList'),
  feedList: document.getElementById('feedList'),
  serverLog: document.getElementById('serverLog'),
  usersCount: document.getElementById('usersCount'),
  postsCount: document.getElementById('postsCount'),
  feedCount: document.getElementById('feedCount'),
};

function logServerResponse(title, data) {
  const content = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  els.serverLog.textContent = `[${new Date().toLocaleTimeString()}] ${title}\n${content}`;
}

function showEmpty(target, message) {
  target.innerHTML = `<div class="empty">${message}</div>`;
}

function safeArray(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.data)) return data.data;
  if (Array.isArray(data?.users)) return data.users;
  if (Array.isArray(data?.posts)) return data.posts;
  if (Array.isArray(data?.feed)) return data.feed;
  return [];
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  const type = response.headers.get('content-type') || '';

  if (type.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    throw new Error(typeof data === 'string' ? data : JSON.stringify(data));
  }

  return data;
}

function renderUsers(users) {
  els.usersCount.textContent = users.length;
  if (!users.length) return showEmpty(els.usersList, 'Nema korisnika za prikaz.');

  els.usersList.innerHTML = users.map(user => `
    <div class="item">
      <h3>${user.username || user.name || 'Korisnik'}</h3>
      <p><strong>ID:</strong> ${user.id ?? '-'}</p>
      <p><strong>Ime:</strong> ${user.full_name || user.fullName || '-'}</p>
      <p><strong>Email:</strong> ${user.email || '-'}</p>
    </div>
  `).join('');
}

function renderPosts(posts, target = els.postsList, countTarget = els.postsCount) {
  countTarget.textContent = posts.length;
  if (!posts.length) return showEmpty(target, 'Nema objava za prikaz.');

  target.innerHTML = posts.map(post => {
    const imageUrl = post.image_url || post.image || post.media_url || '';
    return `
      <div class="item">
        <h3>Objava #${post.id ?? '-'}</h3>
        <p><strong>Korisnik:</strong> ${post.user_id ?? post.userId ?? '-'}</p>
        <p><strong>Sadržaj:</strong> ${post.content || post.caption || '-'}</p>
        <p><strong>Datum:</strong> ${post.created_at || post.timestamp || '-'}</p>
        ${imageUrl ? `<img src="${imageUrl}" alt="post image" />` : ''}
      </div>
    `;
  }).join('');
}

async function loadUsers() {
  try {
    const data = await request(`${API.usersBase()}${API.routes.users}`);
    const users = safeArray(data);
    renderUsers(users);
    logServerResponse('Učitani korisnici', data);
  } catch (error) {
    logServerResponse('Greška pri učitavanju korisnika', error.message);
    showEmpty(els.usersList, 'Greška pri učitavanju korisnika.');
  }
}

async function loadPosts() {
  try {
    const data = await request(`${API.postsBase()}${API.routes.posts}`);
    const posts = safeArray(data);
    renderPosts(posts);
    logServerResponse('Učitane objave', data);
  } catch (error) {
    logServerResponse('Greška pri učitavanju objava', error.message);
    showEmpty(els.postsList, 'Greška pri učitavanju objava.');
  }
}

async function loadFeed(userId) {
  try {
    const data = await request(`${API.feedBase()}${API.routes.feedByUser(userId)}`);
    const feed = safeArray(data);
    els.feedCount.textContent = feed.length;
    renderPosts(feed, els.feedList, els.feedCount);
    logServerResponse(`Učitan feed za korisnika ${userId}`, data);
  } catch (error) {
    els.feedCount.textContent = '0';
    logServerResponse('Greška pri učitavanju feed-a', error.message);
    showEmpty(els.feedList, 'Greška pri učitavanju feed-a.');
  }
}

async function createUser(event) {
  event.preventDefault();
  const formData = new FormData(event.target);
  const payload = Object.fromEntries(formData.entries());

  try {
    const data = await request(`${API.usersBase()}${API.routes.users}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    logServerResponse('Korisnik dodat', data);
    event.target.reset();
    loadUsers();
  } catch (error) {
    logServerResponse('Greška pri dodavanju korisnika', error.message);
  }
}

async function followUser(event) {
  event.preventDefault();
  const formData = new FormData(event.target);
  const payload = Object.fromEntries(formData.entries());

  try {
    const data = await request(`${API.usersBase()}${API.routes.follow}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    logServerResponse('Praćenje sačuvano', data);
    event.target.reset();
  } catch (error) {
    logServerResponse('Greška pri praćenju korisnika', error.message);
  }
}

async function createPost(event) {
  event.preventDefault();
  const formData = new FormData(event.target);

  try {
    const data = await request(`${API.postsBase()}${API.routes.posts}`, {
      method: 'POST',
      body: formData,
    });
    logServerResponse('Objava dodata', data);
    event.target.reset();
    loadPosts();
  } catch (error) {
    logServerResponse('Greška pri dodavanju objave', error.message);
  }
}

function bindEvents() {
  document.getElementById('createUserForm').addEventListener('submit', createUser);
  document.getElementById('followForm').addEventListener('submit', followUser);
  document.getElementById('createPostForm').addEventListener('submit', createPost);
  document.getElementById('feedForm').addEventListener('submit', (event) => {
    event.preventDefault();
    const userId = new FormData(event.target).get('user_id');
    loadFeed(userId);
  });

  document.getElementById('loadUsersBtn').addEventListener('click', loadUsers);
  document.getElementById('loadPostsBtn').addEventListener('click', loadPosts);
  document.getElementById('reloadAllBtn').addEventListener('click', () => {
    loadUsers();
    loadPosts();
  });
  document.getElementById('clearFeedBtn').addEventListener('click', () => {
    els.feedList.innerHTML = '';
    els.feedCount.textContent = '0';
    showEmpty(els.feedList, 'Feed je obrisan iz prikaza.');
  });
  document.getElementById('clearLogBtn').addEventListener('click', () => {
    els.serverLog.textContent = 'Spremno.';
  });
}

function init() {
  bindEvents();
  showEmpty(els.usersList, 'Klikni na “Učitaj korisnike”.');
  showEmpty(els.postsList, 'Klikni na “Učitaj objave”.');
  showEmpty(els.feedList, 'Unesi ID korisnika i učitaj feed.');
}

init();
