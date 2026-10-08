# Demo video script (under 3:00)

Record the deployed app in a browser at 1920×1080. Keep the cursor slow. Speak over the screen.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:20 | Map playing, plume drifting south-east | "Every autumn, stubble fires in Punjab and Haryana send smoke over millions of people. Satellites see every fire, but nobody tells a school principal when the smoke will arrive." |
| 0:20–0:45 | Click a city in the list, its chart and source lines | "ParaliTrace follows the smoke. Every fire releases particles that ride the wind forecast for 48 hours. For Panipat it says when the smoke peaks, and exactly which districts it comes from." |
| 0:45–1:15 | Plan tab, press Plan tomorrow, green rings appear | "Smoke already in the air can't be stopped, but tomorrow's fires can. With 150 field-team locations, the plan avoids [[X]]% of tomorrow's preventable exposure. Sending the same teams to the biggest fires manages [[Y]]%." |
| 1:15–1:45 | Ask tab, the Punjabi school advisory | "Officials and principals can just ask. The assistant runs on the Strands Agents SDK and Amazon Bedrock, and only quotes numbers the model produced, here as a school advisory in Punjabi." |
| 1:45–2:25 | Proof tab, summary, then one city's season chart | "Does it work? I replayed the 2025 season against ground monitors. It caught [[n]] of [[m]] smoke-spike days a day ahead, and [[k]] episode starts, which simply repeating yesterday can never catch." |
| 2:25–2:50 | Architecture: How it works dialog, then the EC2 console briefly | "It runs on AWS: EC2 serves the app and pulls fresh NASA fires and winds every hour, Bedrock powers the assistant. The data is public and the code is open." |
| 2:50–3:00 | Title back on the map | "ParaliTrace. Follow the smoke, stop the right fires." |

Before recording: run `--mode live` so the map shows real fires, close other tabs, and check the
YouTube link opens in a signed-out browser after upload.
