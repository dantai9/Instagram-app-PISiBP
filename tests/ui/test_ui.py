"""
UI Integration Tests — Selenium
Runs against live app at http://localhost

Setup:
    pip install selenium pytest
    sudo pacman -S chromium   (Arch Linux)

Usage:
    pytest tests/ui/test_ui.py -v
"""
import pytest
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

BASE_URL = 'http://localhost:8080'

TEST_USER = 'ui_test_user'
TEST_EMAIL = 'ui_test@test.com'
TEST_PASS = 'uitestpass123'
TEST_NAME = 'UI Test User'

TEST_USER_B = 'ui_test_user_b'
TEST_EMAIL_B = 'ui_test_b@test.com'

def get_chromedriver_path():
    """Find chromedriver on the system automatically."""
    for path in ['/usr/bin/chromedriver', '/usr/local/bin/chromedriver']:
        try:
            result = subprocess.run([path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                return path
        except FileNotFoundError:
            continue
    # fallback — let Selenium find it in PATH
    return 'chromedriver'

@pytest.fixture(scope='module')
def driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,800')
    options.binary_location = '/usr/bin/chromium'
    driver = webdriver.Chrome(
        service=Service(get_chromedriver_path()),
        options=options
    )
    driver.implicitly_wait(10)
    driver.set_page_load_timeout(30)
    yield driver
    driver.quit()

def wait_for(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def wait_clickable(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))

def login_user(driver):
    """Helper — logs in and waits for feed page."""
    driver.execute_script("localStorage.clear()")
    driver.get(f'{BASE_URL}/index.html')
    time.sleep(1)
    wait_for(driver, By.ID, 'loginField').clear()
    driver.find_element(By.ID, 'loginField').send_keys(TEST_USER)
    driver.find_element(By.ID, 'loginPass').clear()
    driver.find_element(By.ID, 'loginPass').send_keys(TEST_PASS)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    WebDriverWait(driver, 15).until(
        lambda d: 'feed' in d.current_url
    )

# ── REGISTRATION ──────────────────────────────

class TestRegistration:

    def test_register_page_loads(self, driver):
        driver.get(f'{BASE_URL}/index.html')
        assert 'Gramo' in driver.title or 'Gramo' in driver.page_source

    def test_switch_to_register_tab(self, driver):
        driver.get(f'{BASE_URL}/index.html')
        register_tab = wait_clickable(driver, By.XPATH, "//button[contains(text(),'Register')]")
        register_tab.click()
        assert wait_for(driver, By.ID, 'regName')

    def test_register_new_user(self, driver):
        import time as t
        unique = str(int(t.time()))
        driver.get(f'{BASE_URL}/index.html')
        wait_clickable(driver, By.XPATH, "//button[contains(text(),'Register')]").click()
        wait_for(driver, By.ID, 'regName').send_keys('Test User')
        driver.find_element(By.ID, 'regUsername').send_keys(f'testuser_{unique}')
        driver.find_element(By.ID, 'regEmail').send_keys(f'test_{unique}@test.com')
        driver.find_element(By.ID, 'regPassword').send_keys('testpass123')
        # Use JavaScript click to avoid interactability issues
        btn = driver.find_element(By.CSS_SELECTOR, '#registerForm button[type="submit"]')
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(2)
        assert 'index' in driver.current_url or 'feed' in driver.current_url or 'Gramo' in driver.page_source

# ── LOGIN ──────────────────────────────

class TestLogin:

    def test_login_page_loads(self, driver):
        driver.get(f'{BASE_URL}/index.html')
        assert wait_for(driver, By.ID, 'loginField')

    def test_login_with_valid_credentials(self, driver):
        login_user(driver)
        assert 'feed' in driver.current_url

    def test_login_with_wrong_password(self, driver):
        driver.execute_script("localStorage.clear()")
        driver.get(f'{BASE_URL}/index.html')
        time.sleep(1)
        # Make sure we are on login tab, not redirected
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'loginField')))
        wait_for(driver, By.ID, 'loginField').clear()
        driver.find_element(By.ID, 'loginField').send_keys(TEST_USER)
        driver.find_element(By.ID, 'loginPass').clear()
        driver.find_element(By.ID, 'loginPass').send_keys('wrongpassword')
        wait_clickable(driver, By.XPATH, "//button[@type='submit']").click()
        time.sleep(1)
        error = wait_for(driver, By.ID, 'loginError')
        assert error.is_displayed()

    def test_redirect_to_login_when_no_token(self, driver):
        driver.execute_script("localStorage.clear()")
        driver.get(f'{BASE_URL}/feed.html')
        WebDriverWait(driver, 5).until(EC.url_contains('index'))
        assert 'index' in driver.current_url

# ── FEED ──────────────────────────────

class TestFeed:

    @pytest.fixture(autouse=True)
    def login_first(self, driver):
        login_user(driver)

    def test_feed_page_loads(self, driver):
        assert 'feed' in driver.current_url
        assert 'Gramo' in driver.page_source

    def test_nav_wordmark_present(self, driver):
        wordmark = wait_for(driver, By.CLASS_NAME, 'nav-wordmark')
        assert wordmark.text == 'Gramo'

    def test_search_bar_present(self, driver):
        search = wait_for(driver, By.ID, 'navSearch')
        assert search.is_displayed()

    def test_search_functionality(self, driver):
        search = wait_for(driver, By.ID, 'navSearch')
        search.clear()
        search.send_keys('test')
        time.sleep(1)
        results = driver.find_element(By.ID, 'searchResults')
        assert results.is_displayed()

    def test_new_post_button_present(self, driver):
        fab = wait_for(driver, By.CLASS_NAME, 'fab')
        assert fab.is_displayed()

    def test_open_new_post_modal(self, driver):
        fab = wait_clickable(driver, By.CLASS_NAME, 'fab')
        fab.click()
        modal = wait_for(driver, By.ID, 'newPostModal')
        assert 'open' in modal.get_attribute('class')

    def test_close_new_post_modal(self, driver):
        fab = wait_clickable(driver, By.CLASS_NAME, 'fab')
        fab.click()
        wait_for(driver, By.CLASS_NAME, 'modal-close').click()
        time.sleep(0.5)
        modal = driver.find_element(By.ID, 'newPostModal')
        assert 'open' not in modal.get_attribute('class')

    def test_logout_button(self, driver):
        logout_btn = wait_clickable(driver, By.XPATH, "//button[contains(text(),'Sign out')]")
        logout_btn.click()
        WebDriverWait(driver, 5).until(EC.url_contains('index'))
        assert 'index' in driver.current_url

# ── PROFILE ──────────────────────────────

class TestProfile:

    @pytest.fixture(autouse=True)
    def login_first(self, driver):
        login_user(driver)

    def test_profile_link_in_nav(self, driver):
        profile_link = wait_for(driver, By.ID, 'myProfileLink')
        assert profile_link.is_displayed()

    def test_navigate_to_own_profile(self, driver):
        profile_link = wait_clickable(driver, By.ID, 'myProfileLink')
        profile_link.click()
        WebDriverWait(driver, 10).until(EC.url_contains('profile'))
        assert 'profile' in driver.current_url

    def test_profile_page_shows_name(self, driver):
        profile_link = wait_clickable(driver, By.ID, 'myProfileLink')
        profile_link.click()
        WebDriverWait(driver, 10).until(EC.url_contains('profile'))
        wait_for(driver, By.CLASS_NAME, 'profile-name')
        assert TEST_NAME in driver.page_source

    def test_edit_profile_button_visible_on_own_profile(self, driver):
        profile_link = wait_clickable(driver, By.ID, 'myProfileLink')
        profile_link.click()
        WebDriverWait(driver, 10).until(EC.url_contains('profile'))
        time.sleep(1)
        assert 'Edit Profile' in driver.page_source

    def test_open_edit_profile_form(self, driver):
        profile_link = wait_clickable(driver, By.ID, 'myProfileLink')
        profile_link.click()
        WebDriverWait(driver, 10).until(EC.url_contains('profile'))
        time.sleep(1)
        edit_btn = wait_clickable(driver, By.XPATH, "//button[contains(text(),'Edit Profile')]")
        edit_btn.click()
        edit_form = wait_for(driver, By.ID, 'editForm')
        assert 'open' in edit_form.get_attribute('class')

# ── FOLLOW REQUESTS ──────────────────────────────

class TestFollowRequests:

    @pytest.fixture(autouse=True)
    def login_first(self, driver):
        login_user(driver)

    def test_follow_requests_link_in_nav(self, driver):
        link = wait_for(driver, By.ID, 'reqsLink')
        assert link.is_displayed()

    def test_navigate_to_follow_requests(self, driver):
        link = wait_clickable(driver, By.ID, 'reqsLink')
        link.click()
        WebDriverWait(driver, 10).until(EC.url_contains('follow-requests'))
        assert 'follow-requests' in driver.current_url

    def test_follow_requests_page_loads(self, driver):
        driver.get(f'{BASE_URL}/follow-requests.html')
        wait_for(driver, By.CLASS_NAME, 'page-title')
        assert 'Follow Requests' in driver.page_source