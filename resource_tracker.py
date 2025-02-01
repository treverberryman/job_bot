from flask import Flask, render_template, jsonify
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd

class JobDatabase:
    def __init__(self, db_path="jobs.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with necessary tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create jobs table
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT,
                url TEXT UNIQUE,
                description TEXT,
                date_posted TEXT,
                source TEXT,
                date_added TEXT,
                job_hash TEXT UNIQUE,
                status TEXT DEFAULT 'new',
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def generate_job_hash(self, job):
        """Create a unique hash for job deduplication"""
        # Combine title and company to create unique identifier
        unique_string = (f"{job['title'].lower().strip()}"
                        f"{job['company'].lower().strip()}"
                        f"{job['description'].lower().strip()}")
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def add_jobs(self, jobs_df):
        """Add new jobs to database with deduplication"""
        conn = sqlite3.connect(self.db_path)
        new_jobs = 0
        duplicates = 0
        
        for _, job in jobs_df.iterrows():
            job_hash = self.generate_job_hash(job)
            
            # Check if job already exists
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jobs WHERE job_hash = ?", (job_hash,))
            exists = cursor.fetchone()
            
            if not exists:
                try:
                    cursor.execute("""
                        INSERT INTO jobs (
                            title, company, url, description,
                            date_posted, source, date_added, job_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job['title'],
                        job['company'],
                        job['url'],
                        job['description'],
                        job['date_posted'],
                        job['source'],
                        datetime.now().isoformat(),
                        job_hash
                    ))
                    new_jobs += 1
                except sqlite3.IntegrityError:
                    duplicates += 1
            else:
                duplicates += 1
        
        conn.commit()
        conn.close()
        return new_jobs, duplicates
    
    def get_all_jobs(self):
        """Retrieve all jobs from database"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT * FROM jobs 
            ORDER BY date_added DESC
        """, conn)
        conn.close()
        return df
    
    def update_job_status(self, job_id, status):
        """Update job status (new, interested, applied, rejected)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()
        conn.close()
    
    def add_job_note(self, job_id, note):
        """Add a note to a job"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE jobs SET notes = ? WHERE id = ?", (note, job_id))
        conn.commit()
        conn.close()

# Flask web interface
app = Flask(__name__)
db = JobDatabase()

@app.route('/')
def index():
    return render_template('jobs.html', jobs=db.get_all_jobs().to_dict('records'))

@app.route('/api/jobs')
def get_jobs():
    return jsonify(db.get_all_jobs().to_dict('records'))

@app.route('/api/jobs/<int:job_id>/status/<status>', methods=['POST'])
def update_status(job_id, status):
    db.update_job_status(job_id, status)
    return jsonify({'success': True})

# HTML template for the web interface
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Job Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-8">Job Tracker</h1>
        
        <div class="grid grid-cols-1 gap-6">
            {% for job in jobs %}
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="flex justify-between items-start">
                    <div>
                        <h2 class="text-xl font-semibold">{{ job.title }}</h2>
                        <p class="text-gray-600">{{ job.company }}</p>
                    </div>
                    <select 
                        class="status-select border rounded p-2"
                        data-job-id="{{ job.id }}"
                        onchange="updateStatus({{ job.id }}, this.value)"
                    >
                        <option value="new" {% if job.status == 'new' %}selected{% endif %}>New</option>
                        <option value="interested" {% if job.status == 'interested' %}selected{% endif %}>Interested</option>
                        <option value="applied" {% if job.status == 'applied' %}selected{% endif %}>Applied</option>
                        <option value="rejected" {% if job.status == 'rejected' %}selected{% endif %}>Rejected</option>
                    </select>
                </div>
                
                <div class="mt-4">
                    <a href="{{ job.url }}" target="_blank" class="text-blue-500 hover:text-blue-700">View Job Post</a>
                    <p class="text-sm text-gray-500 mt-2">Posted: {{ job.date_posted }}</p>
                    <p class="text-sm text-gray-500">Source: {{ job.source }}</p>
                </div>
                
                <div class="mt-4">
                    <textarea 
                        class="w-full p-2 border rounded"
                        placeholder="Add notes..."
                        onchange="updateNotes({{ job.id }}, this.value)"
                    >{{ job.notes or '' }}</textarea>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <script>
    function updateStatus(jobId, status) {
        fetch(`/api/jobs/${jobId}/status/${status}`, {
            method: 'POST'
        });
    }
    
    function updateNotes(jobId, notes) {
        fetch(`/api/jobs/${jobId}/notes`, {
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
with open('templates/jobs.html', 'w') as f:
    f.write(html_template)

# Modified JobSearchTester to use database
class JobSearchTester:
    def __init__(self):
        self.jobs_df = pd.DataFrame()
        self.db = JobDatabase()
    
    # ... (previous JobSearchTester code remains the same)
    
    def save_to_db(self):
        """Save found jobs to database"""
        if not self.jobs_df.empty:
            new_jobs, duplicates = self.db.add_jobs(self.jobs_df)
            print(f"\nSaved to database:")
            print(f"New jobs added: {new_jobs}")
            print(f"Duplicate jobs skipped: {duplicates}")

if __name__ == "__main__":
    # Create database and start web interface
    db = JobDatabase()
    
    # Run job search
    tester = JobSearchTester()
    tester.test_rss_feeds(keywords="python developer", location="remote")
    tester.save_to_db()
    
    # Start web interface
    print("\nStarting web interface on http://localhost:5000")
    app.run(debug=True)
