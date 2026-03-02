import pandas as pd
df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2")
print(df.tail())
