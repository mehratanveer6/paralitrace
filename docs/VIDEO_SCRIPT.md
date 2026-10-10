# Demo video script (under 3:00)

Record the app full screen in your browser (F11), at 1920×1080 if you can. Move the cursor slowly and
pause a beat after each click. Your exact numbers are in `output/SUBMISSION.md`, section 3.

| Time | Do this | Say |
|---|---|---|
| 0:00–0:20 | App open on the replayed day (orange Replay sticker). Press ▶ on the timeline and let the smoke drift. | "Every autumn, stubble fires in Punjab and Haryana send smoke over millions of people. Satellites see every fire, but nobody tells a school principal when the smoke will arrive. This is [replay date], replayed with real NASA fire detections." |
| 0:20–0:45 | Pause. In Cities, click the top city. Its chart and dotted source lines appear. | "ParaliTrace follows the smoke. Every fire releases particles that ride the wind for 48 hours. For this city it shows when the smoke peaks, and exactly which districts it comes from." |
| 0:45–1:20 | Plan tab → **Plan tomorrow**. Green rings appear. Then click **Show the smoke if these fires are stopped**. | "Smoke already in the air can't be stopped, but tomorrow's fires can. With [N] field-team locations, the plan avoids [X]% of tomorrow's preventable exposure; the biggest-fires approach manages [Y]%. And here's the same forecast with those fires stopped." Then read the top two cities from the list. |
| 1:20–1:50 | Ask tab → click **Write a school advisory for Ludhiana in Punjabi.** Wait for the answer, then point at the black tool-call chips. | "Officials can just ask. The assistant is a Strands Agents SDK agent, AWS's open-source agent framework. You can see every tool it calls on the forecast, so it only quotes real numbers, here as a school advisory in Punjabi." |
| 1:50–2:30 | Proof tab. Rest on the top comparison, then scroll to the city chart. | Read the Proof line from SUBMISSION.md, section 3. |
| 2:30–2:50 | Open `paralitrace/agent.py` in your editor: the `from strands import Agent, tool` line, then one `@tool` function. | "Under the hood, Strands runs the agent loop and turns these five Python functions into tools the model can call." |
| 2:50–3:00 | Back in the app, click **Fetch live fires**; today's map loads. | "And it runs live on today's fires. ParaliTrace: follow the smoke, stop the right fires." |

Record with the Windows Game Bar (Win + Alt + R starts and stops; files land in Videos\Captures) or OBS.
Upload to YouTube as **Unlisted**, then open the link in a private window to check it plays.
