import browser_cookie3

cookies = browser_cookie3.chrome(domain_name='intra.42.fr')


session_cookie = None
for cookie in cookies:
    if cookie.name == "_intra_42_session_production":
        session_cookie = cookie.value
        break

if session_cookie:
    print("✅ _intra_42_session_production token found:")
    print(session_cookie)
else:
    print("❌ Cookie not found. Make sure you're logged in to https://intra.42.fr in Chrome.")
