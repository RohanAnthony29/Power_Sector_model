import gridstatus
import pandas as pd
import os

def fetch_pjm_data(year: int = 2023):
    print(f"Initializing PJM gridstatus to fetch load data for {year}...")
    pjm = gridstatus.PJM()
    
    # Fetch historical load - get_load() usually accepts a date or start/end
    # gridstatus.PJM.get_load(start="2023-01-01", end="2023-12-31")
    # Actually for historical hourly, get_load_metered_hourly might be better, or just get_load.
    # We will use get_load with a date range for the specified year.
    start_date = f"{year}-01-01"
    end_date = f"{year+1}-01-01"
    
    print(f"Fetching load from {start_date} to {end_date}. This might take a minute...")
    try:
        # gridstatus handles pagination and API calls
        df = pjm.get_load(start=start_date, end=end_date)
        
        # Ensure output directory exists
        out_dir = "/Users/rohananthony/Downloads/files_new/data"
        os.makedirs(out_dir, exist_ok=True)
        
        out_path = os.path.join(out_dir, f"real_pjm_load_{year}.csv")
        df.to_csv(out_path, index=False)
        print(f"Successfully saved {len(df)} rows to {out_path}")
        
    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == "__main__":
    fetch_pjm_data(2023)
