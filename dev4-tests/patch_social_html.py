"""
patch_social_html.py
Safely add Edit button and editPost() function to social.html.
Handles UTF-16 LE encoding. Only adds — does not remove or reformat anything.
"""
import os

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "social.html")

# Read with correct encoding
with open(HTML_PATH, "r", encoding="utf-16") as f:
    content = f.read()

# Check if edit already exists
if "editPost" in content:
    print("Edit functionality already exists in social.html. No changes needed.")
    exit(0)

# 1. Add Edit button CSS after .btn-delete:hover rule
old_css = ".btn-delete:hover{background:#f85149;color:#fff}"
new_css = old_css + "\n.btn-edit{padding:4px 10px;border:1px solid #58a6ff;background:transparent;color:#58a6ff;border-radius:5px;font-size:.75rem;cursor:pointer;transition:all .2s;margin-right:6px}\n.btn-edit:hover{background:#58a6ff;color:#fff}\n.edit-modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:1000;justify-content:center;align-items:center}\n.edit-modal.active{display:flex}\n.edit-modal-content{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;width:90%;max-width:500px;max-height:80vh;overflow-y:auto}\n.edit-modal-content h3{color:#58a6ff;margin-bottom:16px}\n.edit-modal-content textarea{width:100%;min-height:80px;padding:10px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e1e4e8;font-size:.9rem;resize:vertical;font-family:inherit}\n.edit-modal-content select,.edit-modal-content input{width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e1e4e8;font-size:.85rem;margin-top:4px}\n.edit-modal-content label{display:block;font-size:.8rem;color:#8b949e;margin:12px 0 4px;font-weight:600}\n.edit-actions{display:flex;gap:10px;margin-top:16px}\n.btn-save{padding:10px 20px;border:none;border-radius:6px;background:#238636;color:#fff;font-size:.85rem;font-weight:600;cursor:pointer}\n.btn-save:hover{background:#2ea043}\n.btn-cancel{padding:10px 20px;border:1px solid #30363d;border-radius:6px;background:transparent;color:#8b949e;font-size:.85rem;cursor:pointer}\n.btn-cancel:hover{border-color:#8b949e;color:#e1e4e8}"

assert old_css in content, "Could not find .btn-delete:hover CSS rule"
content = content.replace(old_css, new_css, 1)

# 2. Add Edit button next to Delete button in the table row
old_btn = '<td><button class="btn-delete" onclick="deletePost(${p.id})">Delete</button></td>'
new_btn = '<td><button class="btn-edit" onclick="editPost(${p.id}, p)">Edit</button><button class="btn-delete" onclick="deletePost(${p.id})">Delete</button></td>'
assert old_btn in content, "Could not find Delete button in table"
content = content.replace(old_btn, new_btn, 1)

# 3. Add Status column to table header
old_thead = "<th>Created</th><th></th>"
new_thead = "<th>Status</th><th>Created</th><th></th>"
assert old_thead in content, "Could not find table header"
content = content.replace(old_thead, new_thead, 1)

# 4. Add Status cell to table row (before schedStr)
old_sched_td = "<td>${schedStr}</td>"
new_sched_td = "<td><span style=\"font-size:.75rem;color:${p.status==='scheduled'?'#3fb950':p.status==='published'?'#58a6ff':'#8b949e'}\">${p.status||'draft'}</span></td>\n                <td>${schedStr}</td>"
assert old_sched_td in content, "Could not find scheduled td"
content = content.replace(old_sched_td, new_sched_td, 1)

# 5. Add the edit modal HTML before closing </div> of container
old_container_end = "</div>\n\n<style>"
new_container_end = """</div>

<!-- Edit Post Modal (Dev 4 addition) -->
<div id="editModal" class="edit-modal" onclick="if(event.target===this)closeEditModal()">
  <div class="edit-modal-content">
    <h3>Edit Post</h3>
    <input type="hidden" id="edit-id">
    <label for="edit-content">Content</label>
    <textarea id="edit-content"></textarea>
    <label for="edit-status">Status</label>
    <select id="edit-status">
      <option value="draft">Draft</option>
      <option value="scheduled">Scheduled</option>
      <option value="published">Published</option>
    </select>
    <div class="edit-actions">
      <button class="btn-save" onclick="saveEdit()">Save Changes</button>
      <button class="btn-cancel" onclick="closeEditModal()">Cancel</button>
    </div>
  </div>
</div>

<style>"""

assert old_container_end in content, "Could not find container end pattern"
content = content.replace(old_container_end, new_container_end, 1)

# 6. Add editPost() and saveEdit() functions before the closing </script>
edit_js = """

// --- Edit Post (Dev 4 addition) ---
function editPost(id, post) {
  document.getElementById('edit-id').value = id;
  document.getElementById('edit-content').value = post.content || '';
  document.getElementById('edit-status').value = post.status || 'draft';
  document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
  document.getElementById('editModal').classList.remove('active');
}

async function saveEdit() {
  const id = document.getElementById('edit-id').value;
  const content = document.getElementById('edit-content').value.trim();
  const status = document.getElementById('edit-status').value;
  if (!content) { showFlash('Content cannot be empty.', 'error'); return; }
  try {
    const resp = await fetch(`/api/social/posts/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, status })
    });
    if (resp.ok) {
      showFlash('Post updated.', 'success');
      closeEditModal();
      loadPosts();
    } else {
      const data = await resp.json();
      showFlash(data.error || 'Failed to update post.', 'error');
    }
  } catch (err) {
    showFlash('Network error.', 'error');
  }
}
"""

old_script_end = "</script>\n</body>"
new_script_end = edit_js + "</script>\n</body>"
assert old_script_end in content, "Could not find </script> closing"
content = content.replace(old_script_end, new_script_end, 1)

# Write back with same encoding
with open(HTML_PATH, "w", encoding="utf-16") as f:
    f.write(content)

print("SUCCESS: Added Edit button, modal, and editPost()/saveEdit() to social.html")
print("Changes:")
print("  - Added .btn-edit CSS styles")
print("  - Added Edit modal CSS")
print("  - Added Edit button next to Delete in post table")
print("  - Added Status column to table")
print("  - Added edit modal HTML")
print("  - Added editPost(), closeEditModal(), saveEdit() JS functions")
