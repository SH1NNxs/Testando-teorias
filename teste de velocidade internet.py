import speedtest

st = speedtest.Speedtest()

download_speed = st.download() / 1_000_000  # Convert to Mbps
upload_speed = st.upload() / 1_000_000      # Convert to Mbps
ping = st.results.ping # Ping in ms

print(f"Download Speed: {download_speed:.2f} Mbps")
print(f"Upload Speed: {upload_speed:.2f} Mbps")
print(f"Ping: {ping:.2f} ms")

