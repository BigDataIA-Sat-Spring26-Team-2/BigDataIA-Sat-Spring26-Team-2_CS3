# from apify_client import ApifyClient
# import os
# from dotenv import load_dotenv
# load_dotenv()

# client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

# # Test with Caterpillar
# run_input = {
#     "startUrls": ["https://www.glassdoor.com/Reviews/Walmart-Reviews-E715.htm"],
#     "maxReviews": 5,  # Start with just 5 to test
# }

# print("Starting Glassdoor scrape for walmart")

# run = client.actor("misceres/glassdoor-scraper").call(run_input=run_input)

# print("Scrape complete! Fetching data...")

# # Get results
# for item in client.dataset(run["defaultDatasetId"]).iterate_items():
#     print(f"\n {item.get('rating', 0)}/5 - {item.get('summary', '')}")
#     print(f"   Pros: {item.get('pros', '')[:100]}...")
#     print(f"   Cons: {item.get('cons', '')[:100]}...")


# Find working Glassdoor scrapers
# from apify_client import ApifyClient

# # Initialize the ApifyClient with your Apify API token
# # Replace '<YOUR_API_TOKEN>' with your token.
# client = ApifyClient("apify_api_kvaaLTSsOMjmVbogif3Cw6fyTMLEEu4aBnyX")

# # Prepare the Actor input
# run_input = {
#     "startUrls": [{ "url": "https://www.glassdoor.com/Reviews/JPMorgan-Chase-and-Co-Reviews-E145.htm" }],
#     "includes": [],
#     "proxy": {
#         "useApifyProxy": True,
#         "apifyProxyGroups": ["RESIDENTIAL"],
#     },
# }

# # Run the Actor and wait for it to finish
# run = client.actor("memo23/apify-glassdoor-reviews-scraper").call(run_input=run_input)

# # Fetch and print Actor results from the run's dataset (if there are any)
# print("💾 Check your data here: https://console.apify.com/storage/datasets/" + run["defaultDatasetId"])
# for item in client.dataset(run["defaultDatasetId"]).iterate_items():
#     print(item)





import os
import json
import time
from apify_client import ApifyClient


API_TOKEN = "{API_TOKEN}" 
OUTPUT_FOLDER = "data/glassdoor"
MAX_REVIEWS = 200 
SLEEP_BETWEEN_RUNS = 5  # seconds (avoid rate limits)


COMPANY_URLS = {
    "JPM": "https://www.glassdoor.com/Reviews/JPMorgan-Chase-and-Co-Reviews-E145.htm",
    "WMT": "https://www.glassdoor.com/Reviews/Walmart-Reviews-E715.htm",
    "NVDA": "https://www.glassdoor.com/Reviews/NVIDIA-Reviews-E7633.htm",
    "GE": "https://www.glassdoor.com/Reviews/GE-Reviews-E277.htm",
    "DG": "https://www.glassdoor.com/Reviews/Dollar-General-Reviews-E1342.htm",
    "GS": "https://www.glassdoor.com/Reviews/Goldman-Sachs-Reviews-E2800.htm",
    "TGT": "https://www.glassdoor.com/Reviews/Target-Reviews-E194.htm",
    "CAT": "https://www.glassdoor.com/Reviews/Caterpillar-Reviews-E14583.htm",
    "DE": "https://www.glassdoor.com/Reviews/Deere-and-Company-Reviews-E1239.htm",
    "UNH": "https://www.glassdoor.com/Reviews/UnitedHealth-Group-Reviews-E1513.htm",
    "HCA": "https://www.glassdoor.com/Reviews/HCA-Healthcare-Reviews-E14106.htm",
    "ADP": "https://www.glassdoor.com/Reviews/ADP-Reviews-E737.htm",
    "PAYX": "https://www.glassdoor.com/Reviews/Paychex-Reviews-E3301.htm",
}


client = ApifyClient(API_TOKEN)

# Ensure folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


for ticker, url in COMPANY_URLS.items():
    print(f"\nFetching reviews for {ticker}...")

    try:
        run_input = {
            "startUrls": [{"url": url}],
            "maxItems": MAX_REVIEWS,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        # Run actor
        run = client.actor("memo23/apify-glassdoor-reviews-scraper").call(
            run_input=run_input
        )

        dataset_id = run["defaultDatasetId"]
        print(f"Dataset ID: {dataset_id}")

        # Fetch dataset items
        reviews = list(client.dataset(dataset_id).iterate_items())

        print(f"Retrieved {len(reviews)} reviews for {ticker}")

        # Save to file
        output_path = os.path.join(
            OUTPUT_FOLDER, f"{ticker.lower()}_glassdoor.json"
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(reviews, f, indent=4, ensure_ascii=False)

        print(f"Saved to: {output_path}")

        # Pause to avoid rate limits
        time.sleep(SLEEP_BETWEEN_RUNS)

    except Exception as e:
        print(f"Error fetching {ticker}: {str(e)}")
