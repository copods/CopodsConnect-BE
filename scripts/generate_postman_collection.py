import json
import re

md_path = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\62d843b4-17dd-4d1a-b8b7-a0cc3497b449\implementation_plan.md"
out_path = r"c:\Users\Lenovo\OneDrive\Desktop\Copods\Repos\CopodsConnect-BE\postman\CopodsConnect_Full_Test_Suite_426_Cases.postman_collection.json"

collection = {
    "info": {
        "name": "CopodsConnect — Full Backend Test Suite (426 Cases)",
        "description": "Exhaustive API test collection derived programmatically from implementation_plan.md",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "item": [],
    "variable": [
        {"key": "base_url", "value": "http://localhost:8000"},
        {"key": "api_prefix", "value": "api/v1"},
        {"key": "super_admin_panel_token", "value": ""},
        {"key": "admin_panel_token", "value": ""},
        {"key": "member_panel_token", "value": ""},
        {"key": "super_admin_app_token", "value": ""},
        {"key": "admin_app_token", "value": ""},
        {"key": "member_app_token", "value": ""},
        {"key": "test_post_id", "value": ""},
        {"key": "test_comment_id", "value": ""},
        {"key": "test_alert_id", "value": ""},
        {"key": "test_appreciation_type_id", "value": ""},
        {"key": "test_appreciation_id", "value": ""},
        {"key": "test_notification_id", "value": ""},
        {"key": "member_id", "value": ""},
        {"key": "nonexistent_id", "value": "00000000-0000-0000-0000-000000000000"}
    ]
}

replacements = {
    r'\{user_id\}': '{{member_id}}',
    r'\{post_id\}': '{{test_post_id}}',
    r'\{comment_id\}': '{{test_comment_id}}',
    r'\{alert_id\}': '{{test_alert_id}}',
    r'\{appreciation_type_id\}': '{{test_appreciation_type_id}}',
    r'\{appreciation_id\}': '{{test_appreciation_id}}',
    r'\{notification_id\}': '{{test_notification_id}}'
}

with open(md_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

module_folder = None
endpoint_folder = None
current_method = "GET"
current_url = ""

for line in lines:
    line = line.strip()
    
    if line.startswith("## Module "):
        module_name = line.replace("## ", "").strip()
        module_folder = {
            "name": module_name,
            "item": []
        }
        collection["item"].append(module_folder)
        endpoint_folder = None
        continue
        
    if line.startswith("### `") and module_folder is not None:
        match = re.search(r"### `([A-Z]+)\s+([^`]+)`(.*)", line)
        if match:
            current_method = match.group(1)
            current_url = match.group(2)
            suffix = match.group(3).strip()
            folder_name = f"{current_method} {current_url} {suffix}".strip()
            
            endpoint_folder = {
                "name": folder_name,
                "item": []
            }
            module_folder["item"].append(endpoint_folder)
        continue
        
    if line.startswith("|") and not line.startswith("| ID |") and not line.startswith("|----") and not line.startswith("|---"):
        if endpoint_folder is not None:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                tc_id = parts[1]
                tc_name = parts[2]
                tc_expected = parts[3]
                
                postman_url = current_url
                if not postman_url.startswith("/"):
                    postman_url = "/" + postman_url
                
                # Replace exact paths with {{variables}} based on replacements
                name_lower = tc_name.lower()
                if 'nonexistent' in name_lower or 'invalid id' in name_lower:
                    postman_url = re.sub(r'\{[^}]+\}', '{{nonexistent_id}}', postman_url)
                else:
                    for pattern, replacement in replacements.items():
                        postman_url = re.sub(pattern, replacement, postman_url)
                
                # Build the fully qualified path array and raw URL
                # Example: /api/v1/users/{{member_id}}
                if not postman_url.startswith("/api/v1"):
                    postman_url = "/api/v1" + postman_url
                
                raw_url = f"{{{{base_url}}}}{postman_url}"
                
                # Postman requires 'path' to be an array of segments without slashes
                path_segments = [seg for seg in postman_url.split('/') if seg]
                
                desc = f"# {tc_id}\n\n**Test Case Scenario:**\n{tc_name}\n\n**Expected Outcome:**\n{tc_expected}"
                
                request = {
                    "name": f"{tc_id} - {tc_name}",
                    "request": {
                        "method": current_method,
                        "url": {
                            "raw": raw_url,
                            "host": ["{{base_url}}"],
                            "path": path_segments
                        },
                        "description": desc
                    }
                }
                
                # Automatically add setup scripts (Postman Tests) to capture IDs from responses
                event_scripts = []
                
                # If creating a post, capture test_post_id
                if current_method == "POST" and "app/posts" in postman_url and not "comments" in postman_url and not "like" in postman_url:
                    event_scripts.append(
                        "const d = pm.response.json().data;\n"
                        "if (d && d.id) { pm.collectionVariables.set('test_post_id', d.id); }"
                    )
                # If creating a comment, capture test_comment_id
                elif current_method == "POST" and "comments" in postman_url:
                    event_scripts.append(
                        "const d = pm.response.json().data;\n"
                        "if (d && d.id) { pm.collectionVariables.set('test_comment_id', d.id); }"
                    )
                # If creating an appreciation, capture test_appreciation_id
                elif current_method == "POST" and "appreciations" in postman_url:
                    event_scripts.append(
                        "const d = pm.response.json().data;\n"
                        "if (d && d.id) { pm.collectionVariables.set('test_appreciation_id', d.id); }"
                    )
                
                if event_scripts:
                    request["event"] = [
                        {
                            "listen": "test",
                            "script": {
                                "type": "text/javascript",
                                "exec": event_scripts
                            }
                        }
                    ]
                
                if current_method in ["POST", "PUT", "PATCH", "DELETE"]:
                    request["request"]["header"] = [{"key": "Content-Type", "value": "application/json"}]
                    
                    # Generate default body based on endpoint
                    body_content = "{\n\n}"
                    url_match = postman_url.lower()
                    
                    if "auth/google/callback" in url_match:
                        body_content = '{\n  "code": "PASTE_CODE_HERE",\n  "platform": "panel"\n}'
                    elif "auth/app/google/verify" in url_match:
                        body_content = '{\n  "idToken": "PASTE_ID_TOKEN_HERE"\n}'
                    elif "users/invite/resend" in url_match:
                        body_content = '{\n  "emails": ["test@copods.co"]\n}'
                    elif "users/invite" in url_match or "users/admins/invite" in url_match:
                        body_content = '{\n  "people": [\n    {"email": "test@copods.co"}\n  ]\n}'
                    elif current_method == "DELETE" and url_match == "/api/v1/users":
                        body_content = '{\n  "userIds": ["{{member_id}}"]\n}'
                    elif "/ban" in url_match:
                        body_content = '{\n  "durationHours": 24,\n  "reason": "Test reason"\n}'
                    elif "/role" in url_match:
                        body_content = '{\n  "role": "ADMIN"\n}'
                    elif "/alerts/" in url_match and "/resolve" in url_match:
                        body_content = '{\n  "action": "restore"\n}'
                    elif "/app/posts/media/upload-url" in url_match or "/app/users/me/picture/upload-url" in url_match:
                        body_content = '{\n  "contentType": "image/jpeg"\n}'
                    elif url_match.endswith("/app/posts"):
                        body_content = '{\n  "caption": "Test post",\n  "type": "USER_POST"\n}'
                    elif "/like" in url_match:
                        body_content = '{\n  "reactionType": "LIKE"\n}'
                    elif "/comments" in url_match:
                        body_content = '{\n  "body": "Test comment!"\n}'
                    elif "/vote" in url_match:
                        body_content = '{\n  "optionId": "PASTE_OPTION_ID"\n}'
                    elif "/extend" in url_match:
                        body_content = '{\n  "newClosesAt": "2027-12-31T23:59:59Z"\n}'
                    elif "/app/appreciations" in url_match:
                        body_content = '{\n  "appreciationTypeId": "{{test_appreciation_type_id}}",\n  "recipientIds": ["{{member_id}}"],\n  "message": "Great job!"\n}'
                    elif "/appreciation-types/reorder" in url_match:
                        body_content = '{\n  "items": [\n    {"id": "{{test_appreciation_type_id}}", "displayOrder": 0}\n  ]\n}'
                    elif "/appreciation-types/" in url_match:
                        body_content = '{\n  "name": "Updated Name",\n  "description": "Updated desc"\n}'
                    elif url_match.endswith("/me"):
                        body_content = '{\n  "name": "Updated Name"\n}'
                    elif url_match.endswith("/me/picture"):
                        body_content = '{\n  "picture": "https://url.to/picture.jpg"\n}'
                    elif current_method == "PATCH" and ("/users/" in url_match and not "users/me" in url_match):
                        body_content = '{\n  "name": "New Name"\n}'

                    # Some DELETE methods don't need bodies unless it's bulk delete
                    if current_method != "DELETE" or body_content != "{\n\n}":
                        request["request"]["body"] = {
                            "mode": "raw",
                            "raw": body_content
                        }
                
                endpoint_folder["item"].append(request)

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)

print(f"Generated {out_path} with completely prefilled URL paths and extraction scripts!")
