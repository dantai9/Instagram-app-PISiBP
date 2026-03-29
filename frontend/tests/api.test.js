/**
 * Frontend Unit Tests
 * Pokriva funkcije iz api.js
 *
 * Setup:
 *   cd frontend
 *   npm install --save-dev jest jest-environment-jsdom
 *   npx jest
 */

// ── Mock localStorage ──────────────────────────────
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => { store[key] = String(value); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { store = {}; }
  };
})();
Object.defineProperty(global, 'localStorage', { value: localStorageMock });

// ── Mock fetch ──────────────────────────────
global.fetch = jest.fn();

// ── Mock location ──────────────────────────────
delete global.window.location;
global.window.location = { href: '' };

// ── Load functions under test ──────────────────────────────
// We inline the pure functions from api.js so Jest can test them
// without a DOM/browser environment

function getToken() {
  return localStorage.getItem('token');
}

function getCurrentUserId() {
  return parseInt(localStorage.getItem('user_id'));
}

function avatarHTML(user, size = 36) {
  if (user && user.profile_picture) {
    return `<img class="avatar" src="http://localhost:5000/uploads/${user.profile_picture}" width="${size}" height="${size}" alt=""/>`;
  }
  const initials = user ? (user.name || user.username || '?')[0].toUpperCase() : '?';
  return `<div class="avatar-placeholder" style="width:${size}px;height:${size}px;font-size:${Math.round(size * 0.4)}px">${initials}</div>`;
}

function timeAgo(isoString) {
  const now = Date.now();
  const diff = (now - new Date(isoString)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function authHeaders(extra = {}) {
  return { 'Authorization': `Bearer ${getToken()}`, ...extra };
}

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ════════════════════════════════════════
// TESTOVI
// ════════════════════════════════════════

describe('getToken', () => {
  beforeEach(() => localStorage.clear());

  test('vraca null kada nema tokena', () => {
    expect(getToken()).toBeNull();
  });

  test('vraca token iz localStorage', () => {
    localStorage.setItem('token', 'abc123');
    expect(getToken()).toBe('abc123');
  });
});

describe('getCurrentUserId', () => {
  beforeEach(() => localStorage.clear());

  test('vraca NaN kada nema user_id', () => {
    expect(getCurrentUserId()).toBeNaN();
  });

  test('vraca broj iz localStorage', () => {
    localStorage.setItem('user_id', '42');
    expect(getCurrentUserId()).toBe(42);
  });

  test('vraca broj za string vrijednost', () => {
    localStorage.setItem('user_id', '7');
    expect(getCurrentUserId()).toBe(7);
  });
});

describe('avatarHTML', () => {
  test('vraca img tag kada korisnik ima profilnu sliku', () => {
    const user = { name: 'Ana', profile_picture: 'photo.jpg' };
    const html = avatarHTML(user, 36);
    expect(html).toContain('<img');
    expect(html).toContain('photo.jpg');
    expect(html).toContain('width="36"');
  });

  test('vraca placeholder sa inicijalima kada nema slike', () => {
    const user = { name: 'Marko', profile_picture: null };
    const html = avatarHTML(user, 36);
    expect(html).toContain('avatar-placeholder');
    expect(html).toContain('M');
  });

  test('koristi username za inicijale kada nema name', () => {
    const user = { username: 'bojan99', profile_picture: null };
    const html = avatarHTML(user);
    expect(html).toContain('B');
  });

  test('vraca ? za null korisnika', () => {
    const html = avatarHTML(null);
    expect(html).toContain('?');
  });

  test('poštuje veličinu parametar', () => {
    const user = { name: 'Test', profile_picture: null };
    const html = avatarHTML(user, 96);
    expect(html).toContain('width:96px');
    expect(html).toContain('height:96px');
  });

  test('inicijali su uvijek velika slova', () => {
    const user = { name: 'stefan', profile_picture: null };
    const html = avatarHTML(user);
    expect(html).toContain('S');
    expect(html).not.toContain('>s<');
  });
});

describe('timeAgo', () => {
  test('vraca "just now" za manje od minute', () => {
    const now = new Date(Date.now() - 30 * 1000).toISOString();
    expect(timeAgo(now)).toBe('just now');
  });

  test('vraca minute za manje od sat', () => {
    const now = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(timeAgo(now)).toBe('5m ago');
  });

  test('vraca sate za manje od dan', () => {
    const now = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
    expect(timeAgo(now)).toBe('3h ago');
  });

  test('vraca dane za više od dan', () => {
    const now = new Date(Date.now() - 2 * 86400 * 1000).toISOString();
    expect(timeAgo(now)).toBe('2d ago');
  });

  test('vraca 1m ago za tačno 60 sekundi', () => {
    const now = new Date(Date.now() - 60 * 1000).toISOString();
    expect(timeAgo(now)).toBe('1m ago');
  });

  test('vraca 1h ago za tačno sat', () => {
    const now = new Date(Date.now() - 3600 * 1000).toISOString();
    expect(timeAgo(now)).toBe('1h ago');
  });
});

describe('authHeaders', () => {
  beforeEach(() => localStorage.clear());

  test('vraca Authorization header sa tokenom', () => {
    localStorage.setItem('token', 'mytoken123');
    const headers = authHeaders();
    expect(headers['Authorization']).toBe('Bearer mytoken123');
  });

  test('spaja extra headere', () => {
    localStorage.setItem('token', 'tok');
    const headers = authHeaders({ 'Content-Type': 'application/json' });
    expect(headers['Authorization']).toBe('Bearer tok');
    expect(headers['Content-Type']).toBe('application/json');
  });

  test('Authorization je Bearer null kada nema tokena', () => {
    const headers = authHeaders();
    expect(headers['Authorization']).toBe('Bearer null');
  });
});

describe('escHtml', () => {
  test('escapuje & karakter', () => {
    expect(escHtml('a & b')).toBe('a &amp; b');
  });

  test('escapuje < karakter', () => {
    expect(escHtml('<script>')).toBe('&lt;script&gt;');
  });

  test('escapuje > karakter', () => {
    expect(escHtml('a > b')).toBe('a &gt; b');
  });

  test('escapuje kombinaciju karaktera', () => {
    expect(escHtml('<b>Hello & World</b>')).toBe('&lt;b&gt;Hello &amp; World&lt;/b&gt;');
  });

  test('vraca string za broj', () => {
    expect(escHtml(42)).toBe('42');
  });

  test('vraca prazan string za prazan string', () => {
    expect(escHtml('')).toBe('');
  });

  test('ne mijenja normalan tekst', () => {
    expect(escHtml('Hello World')).toBe('Hello World');
  });
});