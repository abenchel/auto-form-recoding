from requests import Session
import browser_cookie3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


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


from flask import Flask, request, jsonify, render_template


app = Flask(__name__)

project = ProjectBotter()



@app.route("/", methods=["GET"])
def index():
    login = request.args.get("login", "").strip()
    if login:
        [user, projects] = project.get_list_of_projects(login)
        print(user)
        return render_template("index.html", projects=projects, user=user, login=login)
    return render_template("index.html")



@app.route("/reset", methods=["POST"])
def reset():
    project_links = request.form.getlist("projects")
    child_links = request.form.getlist("children")
    
    
    # Combine all links that need to be reset
    all_links = project_links + child_links
    
    success_count = 0
    error_count = 0

    print("All Links to Reset:", all_links)
    
    for link in all_links:
        if link:
            print(f"Resetting link: {link}")
            success = project.reset(link) 
            success=  True
            if success:
                success_count += 1
                print(f"Successfully reset: {link}")
            else:
                error_count += 1
                print(f"Failed to reset: {link}")
    
    # Return JSON response with results
    return jsonify({
        "success": True,
        "message": f"Reset completed: {success_count} successful, {error_count} failed",
        "success_count": success_count,
        "error_count": error_count
    })

if __name__ == "__main__":
    

    app.run(debug=True, host="0.0.0.0", port=4444)



