"""
Below is an updated version that introduces a 'source_url' column in the data_sources table. This field stores the RSS or API URL for each data source. The 'run_saved_search' logic is updated to parse the saved source_url if it's an RSS feed, rather than using the default set of RSS feeds.

Steps:
1. We add 'source_url' to the data_sources table if not already present.
2. The data_sources form includes a 'source_url' field.
3. If a saved search's data_source_id has a source_type='RSS' and a valid source_url, we parse that feed.
4. If there's no link or the source_type isn't RSS, we fall back to the old approach (or skip fetching).
"""

import feedparser
import pandas as pd
import sqlite3
from flask import Flask, request, render_template, jsonify, redirect, url_for
from datetime import datetime
import re

app = Flask(__name__)
DB_NAME = 'resources.db'

class ResourceSearchTester:
    def __init__(self):
        self.resources_df = pd.DataFrame()

    def test_rss_feeds(self, keywords, location, custom_feed=None):
        print(f"Searching for {keywords} in {location}...")
        # If custom_feed is provided, we parse just that feed.
        # Otherwise, we parse our default set.
        if custom_feed:
            rss_feeds = [custom_feed]
        else:
            formatted_keywords = '+'.join(keywords.split())
            rss_feeds = [
          
            ]

        resources = []
        for feed_url in rss_feeds:
            print(f"\nTrying feed: {feed_url}")
            try:
                feed = feedparser.parse(feed_url)
                print(f"Found {len(feed.entries)} entries")
                for entry in feed.entries:
                    description = entry.get('description', '')
                    if not description and 'summary' in entry:
                        description = entry.get('summary', '')
                    resource = {
                        'title': entry.get('title', 'No Title'),
                        'company': entry.get('author', 'Unknown'),
                        'url': entry.get('link', ''),
                        'description': description,
                        'date_posted': entry.get('published', ''),
                        'source': feed_url.split('/')[2],
                        'location': location,
                        'work_status': 'remote' if 'remote' in location.lower() else 'unknown'
                    }
                    # Only keep resources containing any of the keywords
                    if any(k.lower() in resource['title'].lower() or k.lower() in resource['description'].lower() for k in keywords.split()):
                        resources.append(resource)
            except Exception as e:
                print(f"Error with feed {feed_url}: {str(e)}")

        self.resources_df = pd.DataFrame(resources)
        if self.resources_df.empty:
            self.resources_df = pd.DataFrame(columns=[
                'title', 'company', 'url', 'description',
                'date_posted', 'source', 'location', 'work_status'
            ])
            print("\nNo resources found matching criteria.")
        else:
            print(f"\nTotal resources found: {len(self.resources_df)}")
        return self.resources_df

    def filter_resources(self, required_skills=None, exclude_keywords=None):
        if self.resources_df.empty:
            print("No resources to filter - dataframe is empty")
            return self.resources_df
        df = self.resources_df.copy()
        if required_skills:
            print(f"\nFiltering for skills: {required_skills}")
            matching_resources = []
            for _, row in df.iterrows():
                if all(skill.lower() in row['description'].lower() or skill.lower() in row['title'].lower() for skill in required_skills):
                    matching_resources.append(row)
            df = pd.DataFrame(matching_resources)
            print(f"Found {len(df)} resources matching skills")
        if exclude_keywords and not df.empty:
            print(f"\nExcluding keywords: {exclude_keywords}")
            pattern = '|'.join(exclude_keywords)
            df = df[~df['title'].str.contains(pattern, case=False, na=False)]
            df = df[~df['description'].str.contains(pattern, case=False, na=False)]
            print(f"{len(df)} resources remaining after exclusions")
        return df

class resourceTracker:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()

            c.execute("""CREATE TABLE IF NOT EXISTS resources (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT,
                            company TEXT,
                            url TEXT UNIQUE,
                            description TEXT,
                            date_posted TEXT,
                            source TEXT,
                            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )""")

            c.execute("PRAGMA table_info(resources)")
            existing_cols = [row[1] for row in c.fetchall()]
            if "location" not in existing_cols:
                c.execute("ALTER TABLE resources ADD COLUMN location TEXT")
            if "work_status" not in existing_cols:
                c.execute("ALTER TABLE resources ADD COLUMN work_status TEXT")

            # Create a data_sources table.
            c.execute("""CREATE TABLE IF NOT EXISTS data_sources (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            source_type TEXT,
                            best_for TEXT,
                            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )""")

            # Add 'source_url' to data_sources if not present
            c.execute("PRAGMA table_info(data_sources)")
            ds_existing_cols = [row[1] for row in c.fetchall()]
            if "source_url" not in ds_existing_cols:
                c.execute("ALTER TABLE data_sources ADD COLUMN source_url TEXT")

            # Create or alter searches table.
            c.execute("""CREATE TABLE IF NOT EXISTS searches (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            keywords TEXT,
                            location TEXT,
                            is_active INTEGER DEFAULT 1,
                            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )""")

            c.execute("PRAGMA table_info(searches)")
            existing_cols_searches = [row[1] for row in c.fetchall()]
            if "data_source_id" not in existing_cols_searches:
                c.execute("ALTER TABLE searches ADD COLUMN data_source_id INTEGER")

            conn.commit()

    # -------------------------------
    # resources
    # -------------------------------
    def add_resource(self, resource):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM resources WHERE url = ?", (resource['url'],))
            existing = c.fetchone()
            if existing:
                return False
            c.execute("""INSERT INTO resources (
                        title, company, url, description, date_posted,
                        source, location, work_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (resource.get('title',''),
                       resource.get('company',''),
                       resource.get('url',''),
                       resource.get('description',''),
                       resource.get('date_posted',''),
                       resource.get('source',''),
                       resource.get('location',''),
                       resource.get('work_status','')))
            conn.commit()
            return True

    def get_resources(self, search_query=None):
        query = """SELECT id, title, company, url, description,
                          date_posted, source, date_added, location, work_status
                   FROM resources"""
        params = []
        if search_query:
            query += " WHERE title LIKE ? OR company LIKE ?"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute(query, params)
            rows = c.fetchall()
        resources_list = []
        for row in rows:
            resources_list.append({
                'id': row[0],
                'title': row[1],
                'company': row[2],
                'url': row[3],
                'description': row[4],
                'date_posted': row[5],
                'source': row[6],
                'date_added': row[7],
                'location': row[8],
                'work_status': row[9],
            })
        return resources_list

    # -------------------------------
    # Data Sources
    # -------------------------------
    def add_data_source(self, name, source_type, best_for, source_url=None):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO data_sources (name, source_type, best_for, source_url)
                         VALUES (?, ?, ?, ?)""",
                      (name, source_type, best_for, source_url))
            conn.commit()
            return c.lastrowid

    def get_data_sources(self):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, source_type, best_for, last_updated, source_url FROM data_sources")
            rows = c.fetchall()
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'name': row[1],
                    'source_type': row[2],
                    'best_for': row[3],
                    'last_updated': row[4],
                    'source_url': row[5]
                })
            return results

    def get_data_source_by_id(self, ds_id):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""SELECT id, name, source_type, best_for, last_updated, source_url
                         FROM data_sources WHERE id = ?""", (ds_id,))
            row = c.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'name': row[1],
                'source_type': row[2],
                'best_for': row[3],
                'last_updated': row[4],
                'source_url': row[5]
            }

    # Additional CRUD if needed.

    # -------------------------------
    # Saved Searches
    # -------------------------------
    def add_search(self, name, keywords, location,
                   is_active=1, data_source_id=None):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO searches (name, keywords, location, is_active, data_source_id)
                         VALUES (?, ?, ?, ?, ?)""",
                      (name, keywords, location, is_active, data_source_id))
            conn.commit()
            return c.lastrowid

    def get_searches(self):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""SELECT s.id, s.name, s.keywords, s.location,
                                s.is_active, s.date_created, s.data_source_id,
                                ds.name AS ds_name, ds.source_type AS ds_type,
                                ds.source_url
                         FROM searches s
                         LEFT JOIN data_sources ds
                         ON s.data_source_id = ds.id""")
            rows = c.fetchall()
            searches = []
            for row in rows:
                searches.append({
                    'id': row[0],
                    'name': row[1],
                    'keywords': row[2],
                    'location': row[3],
                    'is_active': bool(row[4]),
                    'date_created': row[5],
                    'data_source_id': row[6],
                    'data_source_name': row[7],
                    'data_source_type': row[8],
                    'data_source_url': row[9]
                })
            return searches

    def get_search_by_id(self, search_id):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("""SELECT s.id, s.name, s.keywords, s.location,
                                s.is_active, s.date_created, s.data_source_id,
                                ds.source_type, ds.source_url
                         FROM searches s
                         LEFT JOIN data_sources ds ON s.data_source_id = ds.id
                         WHERE s.id = ?""", (search_id,))
            row = c.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'name': row[1],
                'keywords': row[2],
                'location': row[3],
                'is_active': bool(row[4]),
                'date_created': row[5],
                'data_source_id': row[6],
                'data_source_type': row[7],
                'data_source_url': row[8]
            }

    def update_search(self, search_id, name=None, keywords=None,
                      location=None, is_active=None, data_source_id=None):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if keywords is not None:
                updates.append("keywords = ?")
                params.append(keywords)
            if location is not None:
                updates.append("location = ?")
                params.append(location)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
            if data_source_id is not None:
                updates.append("data_source_id = ?")
                params.append(data_source_id)
            if not updates:
                return 0
            query = "UPDATE searches SET " + ", ".join(updates) + " WHERE id = ?"
            params.append(search_id)
            c.execute(query, tuple(params))
            conn.commit()
            return c.rowcount

    def delete_search(self, search_id):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM searches WHERE id = ?", (search_id,))
            conn.commit()
            return c.rowcount

resource_search_tester = resourcesearchTester()
tracker = resourceTracker()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/search', methods=['POST'])
def search_resources():
    keywords = request.form.get('keywords', 'python developer')
    location = request.form.get('location', 'remote')
    resource_search_tester.test_rss_feeds(keywords, location)
    df = resource_search_tester.filter_resources()
    new_count = 0
    for _, row in df.iterrows():
        resource_dict = row.to_dict()
        tracker.add_resource(resource_dict)
        new_count += 1
    return jsonify({
        'message': f"Imported {new_count} new resources.",
        'total_fetched': len(df)
    })

@app.route('/resources', methods=['GET'])
def list_resources():
    query = request.args.get('q')
    results = tracker.get_resources(search_query=query)
    return jsonify(results)

@app.route('/datasources', methods=['GET', 'POST'])
def manage_data_sources():
    if request.method == 'POST':
        name = request.form.get('name', 'My Data Source')
        source_type = request.form.get('source_type', 'RSS')
        best_for = request.form.get('best_for', 'General')
        source_url = request.form.get('source_url', '')
        tracker.add_data_source(name, source_type, best_for, source_url)
        return redirect(url_for('manage_data_sources'))
    ds_list = tracker.get_data_sources()
    return render_template('data_sources.html', data_sources=ds_list)

@app.route('/savedsearches', methods=['GET'])
def show_saved_searches():
    searches = tracker.get_searches()
    data_sources = tracker.get_data_sources()
    return render_template('saved_searches.html', searches=searches, data_sources=data_sources)

@app.route('/savedsearches', methods=['POST'])
def create_saved_search():
    name = request.form.get('name', 'My Search')
    keywords = request.form.get('keywords', '')
    location = request.form.get('location', '')
    is_active = request.form.get('is_active', '1')
    ds_id = request.form.get('data_source_id', '')
    data_source_id = int(ds_id) if ds_id else None
    tracker.add_search(name, keywords, location, is_active, data_source_id)
    return redirect(url_for('show_saved_searches'))

@app.route('/savedsearches/<int:search_id>/delete', methods=['POST'])
def delete_saved_search(search_id):
    tracker.delete_search(search_id)
    return redirect(url_for('show_saved_searches'))

@app.route('/savedsearches/<int:search_id>/edit', methods=['POST'])
def edit_saved_search(search_id):
    name = request.form.get('name')
    keywords = request.form.get('keywords')
    location = request.form.get('location')
    is_active_str = request.form.get('is_active')
    ds_id = request.form.get('data_source_id', '')
    data_source_id = int(ds_id) if ds_id else None
    is_active = None
    if is_active_str is not None:
        is_active = (is_active_str == '1')
    tracker.update_search(search_id, name, keywords, location, is_active, data_source_id)
    return redirect(url_for('show_saved_searches'))

@app.route('/savedsearches/<int:search_id>/run', methods=['POST'])
def run_saved_search(search_id):
    s = tracker.get_search_by_id(search_id)
    if not s:
        return jsonify({"error": "Search not found."}), 404

    if s['data_source_type'] and s['data_source_type'].upper() == 'RSS':
        # If there's a custom URL, parse that. Otherwise fallback.
        feed_url = s['data_source_url'] or None
        keywords = s['keywords'] or 'python'
        location = s['location'] or 'remote'
        resource_search_tester.test_rss_feeds(keywords, location, custom_feed=feed_url)
        df = resource_search_tester.filter_resources()
        for _, row in df.iterrows():
            tracker.add_resource(row.to_dict())
        return redirect(url_for('show_saved_searches'))
    elif s['data_source_type'] and s['data_source_type'].upper() == 'API':
        # Placeholder for future logic: e.g. requests to an external API.
        return redirect(url_for('show_saved_searches'))
    else:
        return redirect(url_for('show_saved_searches'))

@app.route('/api/savedsearches', methods=['GET'])
def list_savedsearches_json():
    searches = tracker.get_searches()
    return jsonify(searches)

@app.route('/api/resources_for_searches', methods=['POST'])
def resources_for_searches():
    data = request.get_json()
    search_ids = data.get('search_ids', [])
    all_keywords = []
    for sid in search_ids:
        s = tracker.get_search_by_id(sid)
        if s and s['keywords']:
            all_keywords.extend(s['keywords'].split())
    if not all_keywords:
        return jsonify([])
    all_resources = tracker.get_resources()
    matched = []
    for resource in all_resources:
        text_combo = (resource['title'] + ' ' + resource['description']).lower()
        if any(k.lower() in text_combo for k in all_keywords):
            matched.append(resource)
    return jsonify(matched)

@app.route('/test')
def test_endpoint():
    return "This is a test endpoint."

if __name__ == "__main__":
    app.run(debug=True, port=5000)
