import pandas as pd
import io

try:
    # Try reading with different engines if necessary, but usually it's just a path or lock issue
    df = pd.read_excel('assets/data/egressados.xlsx')
    print("COLUMNS:" + str(df.columns.tolist()))
    print("SAMPLE_ROW:" + str(df.head(1).to_dict(orient='records')))
except Exception as e:
    print("ERROR:" + str(e))
