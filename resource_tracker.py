from flask import Flask, render_template, jsonify
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd

class resourceDatabase:
    def __init__(self, db_path="resources.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with necessary tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create resources table
        c.execute('''
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT,
                url TEXT UNIQUE,
                description TEXT,
                date_posted TEXT,
                source TEXT,
                date_added TEXT,
                resource_hash TEXT UNIQUE,
                status TEXT DEFAULT 'new',
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def generate_resource_hash(self, resource):
        """Create a unique hash for resource deduplication"""
        # Combine title and company to create unique identifier
        unique_string = (f"{resource['title'].lower().strip()}"
                        f"{resource['company'].lower().strip()}"
                        f"{resource['description'].lower().strip()}")
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def add_resources(self, resources_df):
        """Add new resources to database with deduplication"""
        conn = sqlite3.connect(self.db_path)
        new_resources = 0
        duplicates = 0
        
        for _, resource in resources_df.iterrows():
            resource_hash = self.generate_resource_hash(resource)
            
            # Check if resource already exists
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM resources WHERE resource_hash = ?", (resource_hash,))
            exists = cursor.fetchone()
            
            if not exists:
                try:
                    cursor.execute("""
                        INSERT INTO resources (
                            title, company, url, description,
                            date_posted, source, date_added, resource_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        resource['title'],
                        resource['company'],
                        resource['url'],
                        resource['description'],
                        resource['date_posted'],
                        resource['source'],
                        datetime.now().isoformat(),
                        resource_hash
                    ))
                    new_resources += 1
                except sqlite3.IntegrityError:
                    duplicates += 1
            else:
                duplicates += 1
        
        conn.commit()
        conn.close()
        return new_resources, duplicates
    
    def get_all_resources(self):
        """Retrieve all resources from database"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT * FROM resources 
            ORDER BY date_added DESC
        """, conn)
        conn.close()
        return df
    
    def update_resource_status(self, resource_id, status):
        """Update resource status (new, interested, applied, rejected)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE resources SET status = ? WHERE id = ?", (status, resource_id))
        conn.commit()
        conn.close()
    
    def add_resource_note(self, resource_id, note):
        """Add a note to a resource"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE resources SET notes = ? WHERE id = ?", (note, resource_id))
        conn.commit()
        conn.close()

# Flask web interface
app = Flask(__name__)
db = resourceDatabase()

@app.route('/')
def index():
    return render_template('resources.html', resources=db.get_all_resources().to_dict('records'))

@app.route('/api/resources')
def get_resources():
    return jsonify(db.get_all_resources().to_dict('records'))

@app.route('/api/resources/<int:resource_id>/status/<status>', methods=['POST'])
def update_status(resource_id, status):
    db.update_resource_status(resource_id, status)
    return jsonify({'success': True})

# HTML template for the web interface
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>resource Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-8">resource Tracker</h1>
        
        <div class="grid grid-cols-1 gap-6">
            {% for resource in resources %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="flex justify-between items-start">
                    <div>
                        <h2 class="text-xl font-semibold">{{ resource.title }}</h2>
                        <p class="text-gray-600">{{ resource.company }}</p>
                    </div>
                    <select 
                        class="status-select border rounded p-2"
                        data-resource-id="{{ resource.id }}"
                        onchange="updateStatus({{ resource.id }}, this.value)"
                    >
                        <option value="new" {% if resource.status == 'new' %}selected{% endif %}>New</option>
                        <option value="interested" {% if resource.status == 'interested' %}selected{% endif %}>Interested</option>
                        <option value="applied" {% if resource.status == 'applied' %}selected{% endif %}>Applied</option>
                        <option value="rejected" {% if resource.status == 'rejected' %}selected{% endif %}>Rejected</option>
                    </select>
                </div>
                
                <div class="mt-4">
                    <a href="{{ resource.url }}" target="_blank" class="text-blue-500 hover:text-blue-700">View resource Post</a>
                    <p class="text-sm text-gray-500 mt-2">Posted: {{ resource.date_posted }}</p>
                    <p class="text-sm text-gray-500">Source: {{ resource.source }}</p>
                </div>
                
                <div class="mt-4">
                    <textarea 
                        class="w-full p-2 border rounded"
                        placeholder="Add notes..."
                        onchange="updateNotes({{ resource.id }}, this.value)"
                    >{{ resource.notes or '' }}</textarea>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <script>
    function updateStatus(resourceId, status) {
        fetch(`/api/resources/${resourceId}/status/${status}`, {
            method: 'POST'
        });
    }
    
    function updateNotes(resourceId, notes) {
        fetch(`/api/resources/${resourceId}/notes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({notes: notes})
        });
    }
    </script>
</body>
</html>
"""

# Save the template
with open('templates/resources.html', 'w') as f:
    f.write(html_template)

# Modified resourcesearchTester to use database
class resourcesearchTester:
    def __init__(self):
        self.resources_df = pd.DataFrame()
        self.db = resourceDatabase()
    
    # ... (previous resourcesearchTester code remains the same)
    
    def save_to_db(self):
        """Save found resources to database"""
        if not self.resources_df.empty:
            new_resources, duplicates = self.db.add_resources(self.resources_df)
            print(f"\nSaved to database:")
            print(f"New resources added: {new_resources}")
            print(f"Duplicate resources skipped: {duplicates}")

if __name__ == "__main__":
    # Create database and start web interface
    db = resourceDatabase()
    
    # Run resource search
    tester = resourcesearchTester()
    tester.test_rss_feeds(keywords="python developer", location="remote")
    tester.save_to_db()
    
    # Start web interface
    print("\nStarting web interface on http://localhost:5000")
    app.run(debug=True)
