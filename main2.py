from flask import Flask, request, jsonify, render_template, session, redirect  # Added 'session' here
import webbrowser
from threading import Timer
from requests import Session
import browser_cookie3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

# Global variable to store the last submitted login
CURRENT_LOGIN = None

# 42 Intra Bot Setup
def get_intra_session_cookie():
    cookies = browser_cookie3.chrome(domain_name='intra.42.fr')
    for cookie in cookies:
        if cookie.name == "_intra_42_session_production":
            return cookie.value
    raise Exception("❌ _intra_42_session_production cookie not found. Make sure you're logged in to intra.42.fr in Chrome.")

INTRA_SESSION = (
    get_intra_session_cookie()  # replace it with _intra_42_session_production
)


def group_projects(projects):
    # Dictionary to store grouped projects
    grouped = {}
    
    for project in projects:
        name = project['name']
        
        # Extract base name (remove #X suffix if present)
        if ' #' in name:
            base_name = name.split(' #')[0]
        else:
            base_name = name
        
        # Initialize group if not exists
        if base_name not in grouped:
            grouped[base_name] = {
                'parent': None,
                'children': []
            }
        
        # Determine if this is parent or child
        if name == base_name:  # This is the parent (no #X suffix)
            grouped[base_name]['parent'] = project
        else:  # This is a child (has #X suffix)
            grouped[base_name]['children'].append(project)
    
    # Transform to the desired format
    result = []
    for base_name, group in grouped.items():
        if group['parent']:  # Only include groups that have a parent
            project_entry = {
                'name': base_name,
                'link': group['parent']['link'],
                'mark': group['parent']['mark'],
                'children': group['children']
            }
            result.append(project_entry)
        elif group['children']:  # If no parent but has children, use first child as parent
            first_child = group['children'][0]
            project_entry = {
                'name': base_name,
                'link': first_child['link'],
                'mark': first_child['mark'],
                'children': group['children'][1:]  # Remaining children
            }
            result.append(project_entry)
    
    return result

class ProjectBotter(Session):
    def __init__(self):
        super().__init__()
        # self.base_url = "https://projects.intra.42.fr/"
        self.set_scoped_base_url("projects")
        self.session_id = INTRA_SESSION
        self.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })
        self.authenticate()

    def request(self, method, url, *args, **kwargs):
        joined_url = urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)

    def set_scoped_base_url(self, scope: str):
        self.base_url = f"https://{scope}.intra.42.fr/"

    def authenticate(self):
        self.cookies.update({"_intra_42_session_production": self.session_id})
        self.headers["X-Csrf-Token"] = self.get_csrf_token()
        return True

    def get_csrf_token(self):
        resp = self.get("/", allow_redirects=False)
        if resp.is_redirect:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_meta = soup.find("meta", attrs={"name": "csrf-token"})
        return csrf_meta.get("content")

    def get_list_of_projects(self, login: str) -> list[{"name": str, "link": str, "mark": str, "children": list}]:
        self.set_scoped_base_url("profile")
        resp = self.get(f"/users/{login}")
        

        soup = BeautifulSoup(resp.text, "html.parser")
        projects = soup.select("#marks div .project-item")



        user_image_el = soup.select_one(".user-image")
        user_name_el = soup.select_one(".name")

        if not user_image_el or not user_name_el:
            return [{
                "name": "Awbx King",
                "user_image": "https://cdn.intra.42.fr/users/7701e713f6b8cb9c5c3b067ab2cba27c/2destiny.jpg",
            }, group_projects([])]

        user_image_style_attr = user_image_el.get("style", "")
        user_image_url = re.search(r'url\((.*?)\)', user_image_style_attr)
        image_url = user_image_url.group(1) if user_image_url else "https://cdn.intra.42.fr/users/7701e713f6b8cb9c5c3b067ab2cba27c/2destiny.jpg"

        user_name = user_name_el.get_text(strip=True) or "Awbx King"

        arr = []
        for project in projects:
            link = project.find("a")
            mark = project.select_one(".pull-right")

            name = link.get_text(strip=True)
            href = link.get("href", "")
            if name.lower().startswith("c piscine exam") or name.lower().startswith("c piscine final exam"):
                continue
            arr.append({
                "name": name,
                "link": href,
                "mark": int(mark.get_text(strip=True) if mark else "0"),
            })
        return [{
            "name": user_name,
            "user_image": image_url,
        }, group_projects(arr)]

    def reset(self, link: str):
        self.set_scoped_base_url("projects")
        matched = re.match(
            r"^https://projects.intra.42.fr/projects/([^\n]+)/projects_users/([0-9]+)$",
            link,
        )
        if not matched:
            return False
        project_name, project_id = matched.groups()
        resp = self.post(
            f"/projects/{project_name}/projects_users/{project_id}/reset",
            allow_redirects=False,
        )
        print("Status Code", resp.status_code)
        return resp.status_code in [200, 302]  # Success or redirect


# Initialize bot

app = Flask(__name__)
app.secret_key = 'hy'  # <-- Add this line

project = ProjectBotter()
@app.route("/", methods=["GET"])
def index():
    login = request.args.get("login", "").strip()
    
    if login:
        # Get user projects from 42 API
        [user, projects] = project.get_list_of_projects(login)
        
        # Get failed projects from global store
        failed_projects = USER_PROJECTS_STORE.get(login, [])
        
        print(f"🔍 Checking projects for {login}")
        print(f"📋 Failed projects from store: {failed_projects}")
        
        # DEBUG: Print what will be sent to template
        print(f"📤 Sending to template: {failed_projects}")
        
        return render_template("index.html", 
                           projects=projects,
                           user=user,
                           login=login,
                           failed_projects=failed_projects,  # Make sure this is correct
                           all_projects_count=len(projects))
    
    return render_template("index.html")

# @app.route("/", methods=["GET"]) also work 
# def index():
#     login = request.args.get("login", "").strip()
#     projects_param = request.args.get("projects", "")
    
#     if login:
#         # Get user projects from 42 API
#         [user, projects] = project.get_list_of_projects(login)
        
#         # Parse projects from URL parameter
#         failed_projects = []
#         if projects_param:
#             failed_projects = [p.replace("+", " ") for p in projects_param.split(",")]
        
#         print(f"🔍 Checking projects for {login}")
#         print(f"📋 Failed projects from URL: {failed_projects}")
        
#         return render_template("index.html", 
#                            projects=projects,
#                            user=user,
#                            login=login,
#                            failed_projects_list=failed_projects,  # Pass to template
#                            all_projects_count=len(projects))
    
#     return render_template("index.html")

# @app.route("/", methods=["GET"])    also work 
# def index():
#     login = request.args.get("login", "").strip()
    
#     if login:
#         # Debug session data
#         print(f"🎯 Session data: {dict(session)}")
#         print(f"🔍 Looking for login: {login}")
        
#         # Get user projects from 42 API
#         [user, projects] = project.get_list_of_projects(login)
        
#         # Get failed projects from session
#         failed_projects = session.get('failed_projects', [])
        
#         print(f"📋 Failed projects received: {failed_projects}")
#         print(f"📊 All projects from API: {[p['name'] for p in projects]}")
        
#         # Mark projects as checked
#         checked_count = 0
#         for project_group in projects:
#             project_name = project_group['name']
            
#             if project_name in failed_projects:
#                 project_group['checked'] = True
#                 checked_count += 1
#                 print(f"✅ CHECKED: {project_name}")
#             else:
#                 print(f"❌ NOT CHECKED: {project_name}")
            
#             # Check children
#             for child in project_group.get('children', []):
#                 child_name = child['name']
#                 if child_name in failed_projects:
#                     child['checked'] = True
#                     checked_count += 1
#                     print(f"✅ CHECKED CHILD: {child_name}")
        
#         print(f"🔢 Total checked projects: {checked_count}")
        
#         return render_template("index.html", 
#                            projects=projects,
#                            user=user,
#                            login=login,
#                            all_projects_count=len(projects),
#                            checked_count=checked_count)
    
#     return render_template("index.html")



# @app.route('/api/data', methods=['POST']) true work 
# def handle_data():
#     """Endpoint for form submissions from Google Apps Script"""
#     try:
#         data = request.get_json()
#         if not data:
#             return jsonify({"error": "No data provided"}), 400
        
#         # Google Apps Script sends 'username' and 'days'
#         login = data.get('username')  # Changed from 'login' to 'username'
#         failed_projects = data.get('days', [])  # Changed from 'projects' to 'days'
        
#         print(f"📥 Received data - Login: {login}, Projects: {failed_projects}")
        
#         if not login:
#             return jsonify({"error": "Login required"}), 400
        
#         # Store failed projects in session
#         session['failed_projects'] = failed_projects
#         global CURRENT_LOGIN
#         CURRENT_LOGIN = login
        
#         # Open browser with the login after 1 second
#         Timer(1, lambda: webbrowser.open_new(f"http://localhost:4444/?login={login}")).start()
        
#         return jsonify({
#             "status": "success", 
#             "login": login,
#             "received_projects": failed_projects,
#             "redirect_url": f"http://localhost:4444/?login={login}"
#         })
        
#     except Exception as e:
#         print(f"❌ Error in /api/data: {str(e)}")
#         return jsonify({"error": str(e)}), 500


# Global storage for projects
USER_PROJECTS_STORE = {}

@app.route('/api/data', methods=['POST'])
def handle_data():
    """Endpoint for form submissions from Google Apps Script"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        login = data.get('username')
        failed_projects = data.get('days', [])
        
        print(f"📥 Received data - Login: {login}, Projects: {failed_projects}")
        
        if not login:
            return jsonify({"error": "Login required"}), 400
        
        # Store in global variable
        global USER_PROJECTS_STORE
        USER_PROJECTS_STORE[login] = failed_projects
        
        # Open browser with the login
        Timer(1, lambda: webbrowser.open_new(f"http://localhost:4444/?login={login}")).start()
        
        return jsonify({
            "status": "success", 
            "login": login,
            "received_projects": failed_projects
        })
        
    except Exception as e:
        print(f"❌ Error in /api/data: {str(e)}")
        return jsonify({"error": str(e)}), 500


# @app.route("/", methods=["GET"])
# def index():
#     login = request.args.get("login", "").strip()
#     projects_param = request.args.get("projects", "")
    
#     if login:
#         # Get user projects from 42 API
#         [user, projects] = project.get_list_of_projects(login)
        
#         # Parse projects from URL parameter
#         failed_projects = []
#         if projects_param:
#             failed_projects = [p.replace("+", " ") for p in projects_param.split(",")]
        
#         print(f"🔍 Checking projects for {login}")
#         print(f"📋 Failed projects from URL: {failed_projects}")
        
#         # Pass the failed projects list to the template for JavaScript
#         return render_template("index.html", 
#                            projects=projects,
#                            user=user,
#                            login=login,
#                            failed_projects_list=failed_projects,  # Add this
#                            all_projects_count=len(projects))
    
#     return render_template("index.html")

@app.route('/api/submit', methods=['POST'])
def handle_submit():
    """Endpoint for form submissions"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    login = data.get('login')
    failed_projects = data.get('projects', [])
    
    if not login:
        return jsonify({"error": "Login required"}), 400
    
    # Store failed projects in session
    session['failed_projects'] = failed_projects
    global CURRENT_LOGIN
    CURRENT_LOGIN = login
    
    # Open browser with the login after 1 second
    Timer(1, lambda: webbrowser.open_new(f"http://localhost:4444/?login={login}")).start()
    
    return jsonify({
        "status": "success", 
        "login": login,
        "redirect_url": f"http://localhost:4444/?login={login}"
    })

@app.route("/reset", methods=["POST"])
def reset_projects():
    project_links = request.form.getlist("projects")
    child_links = request.form.getlist("children")
    all_links = project_links + child_links
    
    results = []
    for link in all_links:
        if link:
            success = project.reset(link)
            results.append({
                "link": link,
                "status": "success" if success else "failed"
            })
    
    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(port=4444, debug=True)