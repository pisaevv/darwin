# The AI Gateway
for platform teams
Put your full AI stack behind one key. See who is driving spend, cap it before it runs, and send each request to the model that should handle it.
Get startedTalk to sales
Open source. Self-hosted.
Your AI App
Humans
Agents
Machines
AI GATEWAY
Optimization
Observability
Routing
Governance
LLMs
MCPs
Quick start
macOS & LinuxWindowsPython SDK
curl -fsSL https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/scripts/quickstart.sh | shCopied
Testimonial
“LiteLLM gives NVIDIA engineers a single, consistent way to access more than 100 AI model endpoints.”
Ajay DograProduct, NVIDIA
“LiteLLM streamlines the complexities of managing multiple LLM models.”
Mark KoltnukPrincipal Architect, Lemonade
“LiteLLM has let my team provide the latest LLM models to our users, usually within a day of them being released… it has saved us months of work.”
David LeenStaff Software Engineer, Netflix
“If we decide to switch the backend model, it’s a simple configuration update in the gateway; no code changes, procurement cycles, or repetitive security reviews required.”
Dennis HenryProductivity Architect, Okta
“After the company began using router provider LiteLLM, the costs of some advanced AI tasks such as coding fell by as much as 56%.”
Mark AustinVP, AT&T Data Office
Building with LiteLLM?Add your logo
Why LiteLLM
## Give your whole org access to every model, agent, and MCP, then see, control, and optimize every request.
01
### Access: Give your whole company every model.
Put every model, agent, and MCP behind one API and one login. We handle key management and work with the secret manager you already run, so platform teams open access to the whole org without becoming the bottleneck, and developers build in minutes, not a procurement cycle.
- One OpenAI-compatible API to 140+ providers and 1,800+ models. Swap models without changing app code.
- One login with SSO, scoped by team, project, or app.
- Day-zero support for new models, so developers get the latest the day it ships.
- Reach agents and MCP servers through the same gateway, not just LLMs.
- Bring your own internal, fine-tuned, and self-hosted models behind the same key.
KeysCreate KeyEndpointsModelsTeamsTeamMembersMCPAI Hub
Virtual Keys Ask AI Export
+ Create New KeyShowing 1–6 of 6Filters
KeyTeamLast ActiveSpend / Budget
acme-prod-gatewayActivesk-…9f2Aplatform-eng2 min ago$4,182.55 / $10,000
wayne-data-scienceActivesk-…Tt09data-science3 min ago$6,740.15 / $12,000
hooli-data-squadActivesk-…Pq77ai-gatewayjust now$3,301.42 / $8,000
globex-genai-platformActivesk-…7b01ml-platform5 min ago$1,905.20 / $5,000
ci-eval-runnerRate-limitedsk-…Hh55infra7 min ago$58.44 / $250
umbrella-eng-sandboxExpiredsk-…WW21security38 min ago$121.87 / $500
Rows per page: 6Page 1 of 1
Key Ownership
Owned By
YouService AccountAnother UserAgent New
OrganizationAll Organizations
TeamSearch or select a team
Key Details
*Key Namee.g. prod-gateway-key
ModelsSelect models
Leave empty to allow access to all models
Key TypeAI APIs
Optional Settings
CancelCreate Key
Team: All TeamsView: All8 deployments
Public NameProviderModeInput / OutputHealth
gpt-5openai/gpt-5OpenAIChat$1.25 / $10Healthy
gpt-5-miniopenai/gpt-5-miniOpenAIChat$0.25 / $2Healthy
claude-opus-4-8anthropic/claude-opus-4-8AnthropicChat$5 / $25Healthy
claude-sonnet-4-5anthropic/claude-sonnet-4-5AnthropicChat$3 / $15Healthy
gemini-2.5-provertex_ai/gemini-2.5-proVertex AIChat$1.25 / $10Healthy
llama-4-maverickbedrock/llama-4-maverickBedrockChat$0.35 / $1.40Healthy
text-embedding-3-largeopenai/text-embedding-3-largeOpenAIEmbedding$0.13 / —Healthy
claude-opus-4-8 (global)anthropic/claude-opus-4-1AnthropicChat$5 / $25Degraded
Group by: Provider6 providers · 15 models
Anthropic — Bedrockclaude-opus-4-8, claude-sonnet-4-5, claude-haiku-4-5bedrock3
Anthropic — Globalclaude-opus-4-8, claude-opus-4-1-20250805global2
OpenAIgpt-5, gpt-5-mini, gpt-5.5-pro, text-embedding-3-largedirect4
Vertex AIgemini-2.5-pro, gemini-2.5-flashgoogle2
Bedrock / Cloudflarellama-4-maverick, mistral-largerouter2
RRoutersprod-router (load-balanced), cheap-fallbackfallback2
+ Create TeamShowing 1–7 of 7Org: All
TeamMembersModelsKeysSpend / Budget
Pplatform-engteam-2f9a…12All8$18.3K / $40K
Ddata-scienceteam-71c4…965$6.7K / $12K
Aai-gatewayteam-08be…6All4$3.3K / $8K
Mml-platformteam-5d20…846$1.9K / $5K
Ssupport-aiteam-9a11…433$2.6K / ∞
Ssecurityteam-c7f3…522$0.1K / $0.5K
Rresearchteam-3b8d…3All2$0.4K / $2K
Pplatform-engteam-2f9a03c1…ActiveEdit Team
Spend
$18,309
Budget
$40,000
Members
12
Keys
8
ModelsAll Proxy Models
Rate LimitsTPM 2,000,000·RPM 10,000
Guardrailspii-maskingprompt-injectionsecret-detection
Object PermissionsVector Stores · 2MCP Servers · 3
Organizationacme-inc
+ Add Member7 membersTeam: platform-eng
MemberTeam RoleLast Active
ARAna Riveraa.rivera@acme.ioAdmin2 min ago
JMJae Moraj.mora@acme.ioMember18 min ago
SPSam Patels.patel@acme.ioMember1 hr ago
KSKir Singhk.singh@acme.ioMember3 hr ago
DVDevOps Botdevops@acme.ioAdminjust now
CIci-eval-runnerservice accountService7 min ago
LCLee Chenl.chen@acme.ioMember5 hr ago
Team: AllAccess Group: All6 servers
github-mcpSSE
https://mcp.acme.io/github
