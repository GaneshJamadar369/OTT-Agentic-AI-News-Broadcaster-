LOQO AI - News URL to DynamicBroadcast Screenplay Generator
Objective
Build a
multi-agent AI pipeline
that takes a
public news article URL
and converts it into a
1–2 minute TV news style screenplay
for an AI avatar news video.
This is
not
a plain summarization task. The output should behave like a
real newsbroadcast package
, where narration, headlines, subheadlines, and visuals change acrosssegments.
Scope
Must build
Input:
1 public news article URL
Extract article text, title, and source images
Generate a
60–120 second anchor-style narration
Break output into
time-based segments
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 1
Create
changing segment-wise headlines
Create
changing segment-wise subheadlines
Plan where
source article images
should appear
Suggest
AI support visual prompts
where needed
Produce final output in:
human-readable screenplay
structured JSON
Not required
actual video generation
actual AI image generation
TTS / avatar rendering
editing or final export
This task is only about the
planning, orchestration, evaluation, and output design layer
.
Suggested agents
Use
3–4 agents
.
1. Article Extraction Agent
fetches and cleans article text
extracts title, body, source images
2. News Editor Agent
identifies story beats
writes 1–2 minute anchor narration
3. Visual Packaging Agent
plans segment-wise visuals
generates main headline, subheadline, tags
places source images / AI support visuals
4. QA / Evaluation Agent
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 2
checks factual accuracy
checks duration fit
checks visual coverage
checks if headlines/subheadlines match each segment
triggers retry when needed
Workflow requirements
Your solution must include:
LangGraph-based workflow
at least
one sequential flow
at least
one parallel step
evaluation + retry mechanism
conditional edges
LangFuse observability
clear
tool routing/orchestration
Example:
extraction → script generation
visual planning + headline generation in parallel
QA review
retry only weak sections
Conditional edges expectation
Use
conditional edges in LangGraph
so that the workflow does not always follow the samepath.
Examples:
if review passes → go to final output
if narration quality fails → route back only to
News Editor Agent
if visual planning fails → route back only to
Visual Packaging Agent
if all required conditions are satisfied → avoid unnecessary retry edges
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 3
This is important because interns should explore how to
skip paths when conditions aresatisfied
and
reiterate only the weak agent when review fails
.
Example:
extraction → narration generation
visual planning + headline generation in parallel
QA review
conditional edge decides:
finalize
retry editor
retry visual packager
Output format
{ "article_url": "https://example.com/news/city-market-fire", "source_title": "Massive Fire Breaks Out in City Market", "video_duration_sec": 75, "segments": [ { "segment_id": 1, "start_time": "00:00", "end_time": "00:10", "layout": "anchor_left + source_visual_right", "anchor_narration": "Good evening. We begin with breaking news from central Delhi, where a major fire has broken out in a crowded market area.", "main_headline": "Major Fire Hits Delhi Market", "subheadline": "Emergency crews rush to crowded commercial zone", "top_tag": "BREAKING", "left_panel": "AI anchor in studio", "right_panel": "Source article image 1 showing smoke and flames", "source_image_url": "https://example.com/image1.jpg",
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 4
"ai_support_visual_prompt": null, "transition": "cut" }, { "segment_id": 2, "start_time": "00:10", "end_time": "00:22", "layout": "anchor_left + ai_support_visual_right", "anchor_narration": "Officials say multiple fire engines were sent to the scene after thick smoke was seen rising above nearby shops and buildings.", "main_headline": "Multiple Fire Engines Deployed", "subheadline": "Smoke seen rising above nearby shops", "top_tag": "LIVE", "left_panel": "AI anchor in studio", "right_panel": "AI-generated support visual of firefighters battling flames in dense market lanes", "source_image_url": null, "ai_support_visual_prompt": "realistic news-style market fire at night, firefighters, smoke, emergency response, urban India", "transition": "crossfade" }, { "segment_id": 3, "start_time": "00:22", "end_time": "00:35", "layout": "anchor_left + source_visual_right", "anchor_narration": "Early reports suggest that no casualties have been confirmed so far, though authorities are still clearing the area and assessing damage.", "main_headline": "No Casualties Confirmed Yet", "subheadline": "Authorities clear area and assess damage", "top_tag": "DEVELOPING", "left_panel": "AI anchor in studio", "right_panel": "Source article image 2 showing responders and crowd control", "source_image_url": "https://example.com/image2.jpg", "ai_support_visual_prompt": null, "transition": "cut" },
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 5
{ "segment_id": 4, "start_time": "00:35", "end_time": "00:50", "layout": "anchor_left + ai_support_visual_right", "anchor_narration": "Police have also diverted traffic around the market, while local residents and shop owners have been asked to remain at a safe distance.", "main_headline": "Traffic Diverted Near Fire Zone", "subheadline": "Residents and shop owners told to stay back", "top_tag": "UPDATE", "left_panel": "AI anchor in studio", "right_panel": "AI-generated support visual of police barricades and diverted traffic near market", "source_image_url": null, "ai_support_visual_prompt": "realistic police barricades, diverted vehicles, busy market road, emergency perimeter, Indian city, news broadcast style", "transition": "slide" }, { "segment_id": 5, "start_time": "00:50", "end_time": "01:15", "layout": "anchor_left + source_visual_right", "anchor_narration": "Investigators are now looking into what may have caused the blaze. More updates are expected as firefighting operations continue through the evening.", "main_headline": "Cause of Blaze Under Probe", "subheadline": "More updates expected through the evening", "top_tag": "LATEST", "left_panel": "AI anchor in studio", "right_panel": "Source article image 3 or closing live visual", "source_image_url": "https://example.com/image3.jpg", "ai_support_visual_prompt": null, "transition": "fade_out" }
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 6
]}
Evaluation & Retry Expectations
Your system must include a
Reviewer / QA Agent
that scores the generated broadcastscreenplay and triggers
targeted retries
.
Do not accept first output blindly. The goal is to improve quality over
2–3 retry rounds max
.
Reviewer Agent responsibility
The Reviewer Agent should check whether the output feels like a
real short TV newssegment
with:
strong opening
clear middle flow
proper ending
engaging narration
correct visual planning
strong headline/subheadline placement
factual grounding to the source article
Main Evaluation Criteria
Score each criterion from
1 to 5
.
1. Story Structure & Flow
Checks:
Is there a clear
start, middle, ending
?
Does the story progress smoothly?
Does the ending close properly instead of stopping abruptly?
Good
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 7
“Good evening. A major fire broke out…” → impact/details → response/update → closingline.
Bad
Starts with random detail, repeats facts in middle, ends suddenly without closure.
2. Hook & Engagement
Checks:
Does the first 1–2 lines create interest?
Is the narration engaging enough for a news audience?
Does it avoid sounding flat or copied from the article?
Good
“Breaking tonight, panic spread across the market after a major fire…”
Bad
“This article is about a fire incident that happened in the city…”
3. Narration Quality
Checks:
Does it sound like
TV news narration
?
Is the language concise, professional, and easy to speak?
Is there repetition or robotic phrasing?
Good
“Officials say emergency teams reached the scene within minutes.”
Bad
“As per the report it has been stated that according to officials…”
4. Visual Planning & Placement
Checks:
Does every major segment have a clear visual?
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 8
Are source/article images used at the right moments?
Are AI support visuals relevant?
Do visual switches match narration timing?
Good
Opening with anchor + side article image, then support visual during damage description,then back to anchor for close.
Bad
Same visual for entire video, or unrelated AI visual placed in emotional/high-fact segment.
5. Headline / Subheadline Quality
Checks:
Do headlines change by segment?
Do they match the current narration beat?
Are they short, clear, and broadcast-friendly?
Are they placed at the right moments?
Good
Segment 1 headline: “Massive Fire Hits Market”
Segment 2 headline: “Emergency Teams Rush In”
Bad
Same headline across all segments, or overly long lines like:
“Authorities and emergency response teams continue to manage the developing market firesituation tonight”
Extra Important Checks
Reviewer Agent should also check:
Factual grounding
→ no invented claims
Coverage
→ major facts from article are included
Duration fit
→ 60–120 seconds
LOQO AI - News URL to Dynamic Broadcast Screenplay Generator 9
Text fit
→ overlays short enough for screen
Redundancy
→ no repeated facts/headlines/visuals
Timeline coherence
→ narration, visuals, and overlays align properly
Scoring
Give
1–5 score
for each main criterion:
1 = poor
2 = weak
3 = acceptable
4 = good
5 = excellent
Suggested pass rule
No major criterion below
3
Overall average must be
4 or above
Example:
Story Structure: 4
Hook & Engagement: 2
Narration Quality: 4
Visual Planning: 3
Headline Quality: 2
Result:
Fail
Reason: weak hook and weak headline system
LOQO