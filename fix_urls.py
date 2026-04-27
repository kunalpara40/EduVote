import os
import re

template_dir = r"c:\evote\app\templates"

replacements = {
    "'login'": "'voter.login'",
    "'register'": "'voter.register'",
    "'verify_otp'": "'voter.verify_otp'",
    "'logout'": "'voter.logout'",
    "'dashboard'": "'voter.dashboard'",
    "'register_face'": "'voter.register_face'",
    "'verify_face'": "'voter.verify_face'",
    "'vote'": "'voter.vote'",
    "'confirmation'": "'voter.confirmation'",
    "'results'": "'voter.results'",
    "'index'": "'voter.index'",
    "'admin_login'": "'admin.admin_login'",
    "'admin_logout'": "'admin.admin_logout'",
    "'admin_dashboard'": "'admin.admin_dashboard'",
    "'create_election'": "'admin.create_election'",
    "'edit_election'": "'admin.edit_election'",
    "'delete_election'": "'admin.delete_election'",
    "'publish_election'": "'admin.publish_election'",
    "'unpublish_election'": "'admin.unpublish_election'",
    "'declare_results'": "'admin.declare_results'",
    "'undeclare_results'": "'admin.undeclare_results'",
    "'add_candidate'": "'admin.add_candidate'",
    "'delete_candidate'": "'admin.delete_candidate'",
    "'verify_voter'": "'admin.verify_voter'",
    "'delete_voter'": "'admin.delete_voter'"
}

def fix_urls(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".html"):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for old, new in replacements.items():
                    # We match `url_for('name'` instead of `url_for('name')`
                    content = content.replace(f"url_for({old}", f"url_for({new}")
                    old_dq = old.replace("'", '"')
                    new_dq = new.replace("'", '"')
                    content = content.replace(f"url_for({old_dq}", f"url_for({new_dq}")

                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)

if __name__ == "__main__":
    fix_urls(template_dir)
    print("Fixed URLs successfully.")
