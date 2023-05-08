from proventosweb import provlista

# Sample list of stock tickers
acoes = ["ABEV3", "AZUL4", "BTOW3", "B3SA3", "BBSE3"]

# Fetch proventos (dividends) for the list of stock tickers
df_prov = provlista(acoes)

# Print the resulting DataFrame
print(df_prov)
