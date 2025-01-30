#%%
import feedparser
import pandas as pd
from datetime import datetime
import time
import requests
from bs4 import BeautifulSoup
# from pandasgui import show


class JobSearchTester:
    def __init__(self):
        """Initialize with no config required"""
        self.jobs_df = pd.DataFrame()
    
    def test_rss_feeds(self, keywords, location):
        """Test RSS feed parsing with public feeds"""
        print(f"Searching for {keywords} in {location}...")
        
        # Convert keywords for URL formatting
        formatted_keywords = '+'.join(keywords.split())
        
        # List of public RSS feeds that are currently active
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
                    # Different RSS feeds have different structures
                    description = entry.get('description', '')
                    if not description and 'summary' in entry:
                        description = entry.get('summary', '')
                        
                    job = {
                        'title': entry.get('title', 'No Title'),
                        'company': entry.get('author', 'Unknown'),
                        'url': entry.get('link', ''),
                        'description': description,
                        'date_posted': entry.get('published', ''),
                        'source': feed_url.split('/')[2]  # Extract domain name
                    }
                    
                    # Only add jobs that match our keywords (case-insensitive)
                    if any(keyword.lower() in job['title'].lower() or 
                          keyword.lower() in job['description'].lower() 
                          for keyword in keywords.split()):
                        jobs.append(job)
                        # print(f"Found matching job: {job['title']} at {job['company']}")
                    
            except Exception as e:
                print(f"Error with feed {feed_url}: {str(e)}")
        
        # Convert to dataframe
        self.jobs_df = pd.DataFrame(jobs)
        
        # If no jobs found, create empty DataFrame with correct columns
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

# Test the script
if __name__ == "__main__":
    # Initialize tester
    tester = JobSearchTester()
    
    # Test search
    print("Starting job search test...")
    jobs = tester.test_rss_feeds(
        keywords="it support",
        location="remote"  # Note: These feeds are remote-only
    )
    
    # Test filters
    filtered_jobs = tester.filter_jobs(
        required_skills=["python"],
        exclude_keywords=["senior", "lead"]
    )
    
    # Show results
    if not filtered_jobs.empty:
        print("\nFinal Results:")
        print(f"Total jobs found: {len(jobs)}")
        print(f"Jobs after filtering: {len(filtered_jobs)}")
        print("\nSample job titles:")
        for i, (_, row) in enumerate(filtered_jobs.head().iterrows()):
            print(f"{i+1}. {row['title']} at {row['company']}")
            print(f"   Link: {row['url']}\n")
    else:
        print("\nNo jobs found matching criteria")


# %%
