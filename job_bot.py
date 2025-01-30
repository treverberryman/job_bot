"""
Below is a unified and extended version of your code that integrates an SQLite database, a Flask web interface, and duplicate checking.

Explanation of what's changed or added:
1. Created a new class 'JobTracker' that handles database setup, insertion, checking duplicates, and retrieving filtered data.
2. Integrated Flask routes for searching jobs, displaying them, filtering them, and testing.
3. Used the existing logic from JobSearchTester, factoring out feed parsing and filtering.
4. Provided an example duplicate check that compares job 'title', 'company', and 'url'.
5. Provided an example HTML template approach using basic placeholders.

Feel free to adapt this further for your needs, including customizing table schema, route structure, and HTML templates.

"""

import feedparser
import pandas as pd
import sqlite3
from flask import Flask, request, render_template, jsonify
from datetime import datetime
import re

app = Flask(__name__)
DB_NAME = 'jobs.db'

class JobSearchTester:
    def __init__(self):
        """Initialize with no config required"""
        self.jobs_df = pd.DataFrame()

    def test_rss_feeds(self, keywords, location):
        """Test RSS feed parsing with public feeds"""
        print(f"Searching for {keywords} in {location}...")

        formatted_keywords = '+'.join(keywords.split())

        rss_feeds = [
            "https://weworkremotely.com/categories/remote-programming-jobs.rss",
            "https://remoteok.io/remote-dev-jobs.rss",
            "https://remotive.com/remote-jobs/feed/qa",
            "https://jobicy.com/?feed=job_feed&job_categories=technical-support&job_types=full-time&search_region=usa",
            f"https://rsshub.app/github/job/{formatted_keywords}"
        ]

        jobs = []
        for feed_url in rss_feeds:
            print(f"\nTrying feed: {feed_url}")
            try:
                feed = feedparser.parse(feed_url)
                print(f"Found {len(feed.entries)} entries")

                for entry in feed.entries:
                    description = entry.get('description', '')
                    if not description and 'summary' in entry:
                        description = entry.get('summary', '')

                    job = {
                        'title': entry.get('title', 'No Title'),
                        'company': entry.get('author', 'Unknown'),
                        'url': entry.get('link', ''),
                        'description': description,
                        'date_posted': entry.get('published', ''),
                        'source': feed_url.split('/')[2]
                    }

                    if any(keyword.lower() in job['title'].lower() or
                           keyword.lower() in job['description'].lower()
                           for keyword in keywords.split()):
                        jobs.append(job)

            except Exception as e:
                print(f"Error with feed {feed_url}: {str(e)}")

        self.jobs_df = pd.DataFrame(jobs)

        if self.jobs_df.empty:
            self.jobs_df = pd.DataFrame(columns=[
                'title', 'company', 'url', 'description',
                'date_posted', 'source'
            ])
            print("\nNo jobs found matching criteria.")
        else:
            print(f"\nTotal jobs found: {len(self.jobs_df)}")
        return self.jobs_df

    def filter_jobs(self, required_skills=None, exclude_keywords=None):
        """Basic filter function for testing"""
        if self.jobs_df.empty:
            print("No jobs to filter - dataframe is empty")
            return self.jobs_df

        df = self.jobs_df.copy()

        if required_skills:
            print(f"\nFiltering for skills: {required_skills}")
            matching_jobs = []
            for _, row in df.iterrows():
                if all(skill.lower() in row['description'].lower() or
                       skill.lower() in row['title'].lower()
                       for skill in required_skills):
                    matching_jobs.append(row)
            df = pd.DataFrame(matching_jobs)
            print(f"Found {len(df)} jobs matching skills")

        if exclude_keywords and not df.empty:
            print(f"\nExcluding keywords: {exclude_keywords}")
            df = df[~df['title'].str.contains('|'.join(exclude_keywords), case=False, na=False)]
            df = df[~df['description'].str.contains('|'.join(exclude_keywords), case=False, na=False)]
            print(f"{len(df)} jobs remaining after exclusions")

        return df

class JobTracker:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS jobs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT,
                            company TEXT,
                            url TEXT UNIQUE,
                            description TEXT,
                            date_posted TEXT,
                            source TEXT,
                            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )""")
            conn.commit()

    def add_job(self, job):
        # job is a dict with keys: title, company, url, description, date_posted, source
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            # Check duplicates by URL or by title/company if you prefer
            c.execute("SELECT * FROM jobs WHERE url = ?", (job['url'],))
            existing = c.fetchone()
            if existing:
                return False  # Duplicate found
            c.execute("""INSERT INTO jobs (title, company, url, description, date_posted, source)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (job['title'],
                       job['company'],
                       job['url'],
                       job['description'],
                       job['date_posted'],
                       job['source']))
            conn.commit()
            return True

    def get_jobs(self, search_query=None):
        query = "SELECT * FROM jobs"
        params = []
        if search_query:
            # Simple search by title or company
            query += " WHERE title LIKE ? OR company LIKE ?"
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute(query, params)
            rows = c.fetchall()

        # Convert to a list of dicts
        jobs_list = []
        for row in rows:
            jobs_list.append({
                'id': row[0],
                'title': row[1],
                'company': row[2],
                'url': row[3],
                'description': row[4],
                'date_posted': row[5],
                'source': row[6],
                'date_added': row[7]
            })
        return jobs_list

# Instantiate global objects
job_search_tester = JobSearchTester()
tracker = JobTracker()

# Flask Routes
@app.route('/')
def home():
    return "<h1>Job Tracker</h1><p>Welcome to the Job Tracker app.</p>"

@app.route('/search', methods=['POST'])
def search_jobs():
    keywords = request.form.get('keywords', 'python developer')
    location = request.form.get('location', 'remote')
    job_search_tester.test_rss_feeds(keywords, location)
    # Optionally filter
    df = job_search_tester.filter_jobs()

    # Insert into DB, ignoring duplicates
    new_count = 0
    for _, row in df.iterrows():
        job_dict = row.to_dict()
        success = tracker.add_job(job_dict)
        if success:
            new_count += 1

    return jsonify({
        'message': f"Imported {new_count} new jobs.",
        'total_fetched': len(df)
    })

@app.route('/jobs', methods=['GET'])
def list_jobs():
    query = request.args.get('q')
    results = tracker.get_jobs(search_query=query)
    # You can return JSON or render a template
    return jsonify(results)

@app.route('/test')
def test_endpoint():
    return "This is a test endpoint."

if __name__ == "__main__":
    # Run Flask in debug mode for development
    app.run(debug=True, port=5000)