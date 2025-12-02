# AgentCore Memory + Strands Agents SDK Test Cases

## Overview

This document contains test cases for the AgentCore Memory features implemented in the MSP Support Assistant using the **Strands Agents SDK**.

The memory system includes:

- **Short-term Memory**: Conversation history via `AgentCoreMemorySessionManager`
- **Long-term Memory**: Extracted facts, preferences, and summaries via memory strategies
- **Agentic RAG**: `retrieve_memories` tool for proactive memory search

## Technology Stack

| Component | Implementation |
|-----------|----------------|
| **Agent Framework** | Strands Agents SDK (`strands-agents`) |
| **Memory SDK** | `bedrock-agentcore` package |
| **Session Manager** | `AgentCoreMemorySessionManager` |
| **Model** | Amazon Nova Pro via `BedrockModel` |
| **Tools** | `@tool` decorated Python functions |

## Prerequisites

- Strands app running at `http://localhost:8501`
  ```bash
  cd src/streamlit
  AWS_PROFILE=kcom streamlit run strands_app.py --server.port 8501
  ```
- Required packages installed:
  ```bash
  pip install strands-agents strands-agents-tools bedrock-agentcore
  ```
- AWS credentials configured with AgentCore permissions
- Memory ID: `msp_support_assistant_memory-NeCST586bk`

---

## Test Suite 1: Strands + Memory Infrastructure

### TC-MEM-001: Verify Strands SDK Status

**Objective**: Confirm all SDKs are loaded correctly

**Steps**:
1. Open the Streamlit app at http://localhost:8501
2. Check the sidebar "SDK Status" section

**Expected Results**:
- [ ] "Strands SDK: Available" shows as green success indicator
- [ ] "AgentCore SDK: Available" shows as green success indicator
- [ ] "Tools: 6 loaded" shows as green success indicator
- [ ] "Ticket API: Available" shows as green success indicator

**Notes**: If SDKs are not available, run:
```bash
pip install strands-agents strands-agents-tools bedrock-agentcore
```

---

### TC-MEM-002: Verify Memory Settings UI

**Objective**: Confirm memory settings are visible and functional in sidebar

**Steps**:
1. Open the Strands app
2. Look at the sidebar under "Memory Settings"

**Expected Results**:
- [ ] "Your Name/ID" text input is visible with default value "demo-user"
- [ ] "Enable AgentCore Memory" checkbox is visible and checked by default
- [ ] Memory ID shows truncated value
- [ ] "Memory strategies: preferences, facts, summaries" caption visible

---

## Test Suite 2: Short-term Memory (via AgentCoreMemorySessionManager)

### TC-MEM-010: Store Conversation Event - Basic

**Objective**: Verify conversation exchanges are stored via session manager hooks

**Steps**:
1. Open the Strands app
2. Enter "luca" in the "Your Name/ID" field
3. Type "Hello, my name is Luca" in the chat input
4. Press Enter and wait for response

**Expected Results**:
- [ ] Strands Agent responds with a greeting acknowledging the name
- [ ] "Tool Executions" section may show tools used
- [ ] No errors appear in "Agent Errors" expander
- [ ] Event is stored automatically by ShortMemoryHook (verify via AWS CLI below)

**Verification Command**:
```bash
AWS_PROFILE=kcom aws bedrock-agentcore list-events \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --actor-id luca \
  --max-results 5
```

---

### TC-MEM-011: Store Multiple Events in Session

**Objective**: Verify multiple conversation exchanges are stored

**Steps**:
1. Continue from TC-MEM-010 or start fresh with actor "luca"
2. Send message: "I work in the IT support department"
3. Wait for response
4. Send message: "What tickets are open?"
5. Wait for response

**Expected Results**:
- [ ] Each exchange creates a new event
- [ ] Events contain both USER and ASSISTANT messages
- [ ] Session ID remains consistent across exchanges

**Verification Command**:
```bash
AWS_PROFILE=kcom aws bedrock-agentcore list-events \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --actor-id luca \
  --session-id <session-id-from-sidebar>
```

---

### TC-MEM-012: Event Storage with Memory Disabled

**Objective**: Verify events are NOT stored when memory is disabled

**Steps**:
1. Uncheck "Enable Memory" in the sidebar
2. Send a message: "This should not be stored"
3. Wait for response

**Expected Results**:
- [ ] Conversation still works normally
- [ ] No new events are created (verify via AWS CLI)
- [ ] No memory errors appear

---

### TC-MEM-013: Different Actor IDs Create Separate Events

**Objective**: Verify events are isolated by actor ID

**Steps**:
1. Set "Your Name/ID" to "user-alice"
2. Send message: "I'm Alice from accounting"
3. Wait for response
4. Change "Your Name/ID" to "user-bob"
5. Send message: "I'm Bob from engineering"
6. Wait for response

**Expected Results**:
- [ ] Events for "user-alice" only contain Alice's conversation
- [ ] Events for "user-bob" only contain Bob's conversation
- [ ] Events are completely isolated

**Verification Commands**:
```bash
# Check Alice's events
AWS_PROFILE=kcom aws bedrock-agentcore list-events \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --actor-id user-alice

# Check Bob's events
AWS_PROFILE=kcom aws bedrock-agentcore list-events \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --actor-id user-bob
```

---

## Test Suite 3: Long-term Memory (Memory Strategies)

### TC-MEM-020: User Preference Extraction

**Objective**: Verify user preferences are extracted and stored

**Steps**:
1. Set actor ID to "test-prefs"
2. Send message: "I always prefer high priority tickets to be handled first"
3. Wait for response
4. Send message: "I like detailed explanations in responses"
5. Wait ~5 minutes for extraction to process

**Expected Results**:
- [ ] Preferences are extracted to `/preferences/test-prefs` namespace
- [ ] Memory records contain preference information

**Verification Command**:
```bash
AWS_PROFILE=kcom aws bedrock-agentcore list-memory-records \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --namespace "/preferences/test-prefs"
```

---

### TC-MEM-021: Semantic Fact Extraction

**Objective**: Verify factual information is extracted and stored

**Steps**:
1. Set actor ID to "test-facts"
2. Send message: "My name is Giovanni and I'm the IT Director"
3. Wait for response
4. Send message: "My employee ID is EMP-12345"
5. Wait for response
6. Wait ~5 minutes for extraction to process

**Expected Results**:
- [ ] Facts are extracted to `/facts/test-facts` namespace
- [ ] Memory records contain: name, role, employee ID

**Verification Command**:
```bash
AWS_PROFILE=kcom aws bedrock-agentcore list-memory-records \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --namespace "/facts/test-facts"
```

---

### TC-MEM-022: Session Summary Extraction

**Objective**: Verify session summaries are created

**Steps**:
1. Set actor ID to "test-summary"
2. Have a multi-turn conversation (5+ exchanges) about a specific topic
3. Example conversation:
   - "I need help with a printer issue"
   - "The printer is HP LaserJet in room 201"
   - "It's showing paper jam error but no paper is jammed"
   - "I've tried turning it off and on"
   - "The error persists"
4. End the session (close browser or clear chat)
5. Wait ~5 minutes for extraction

**Expected Results**:
- [ ] Summary is created in `/summaries/test-summary/{sessionId}` namespace
- [ ] Summary captures the key points of the conversation

**Verification Command**:
```bash
AWS_PROFILE=kcom aws bedrock-agentcore list-memory-records \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --namespace "/summaries/test-summary"
```

---

### TC-MEM-023: Memory Retrieval on New Session

**Objective**: Verify long-term memories are retrieved in new sessions

**Prerequisites**: Complete TC-MEM-021 first and wait for extraction

**Steps**:
1. Close browser completely
2. Reopen Streamlit app
3. Set actor ID to "test-facts" (same as TC-MEM-021)
4. Check sidebar for memory record count
5. Send message: "What do you remember about me?"

**Expected Results**:
- [ ] Memory record count shows > 0 records
- [ ] Assistant recalls previously stored facts (name, role, etc.)
- [ ] Response is personalized based on memory context

---

## Test Suite 4: Memory Context Integration

### TC-MEM-030: System Prompt Includes Memory Context

**Objective**: Verify memory context is injected into system prompt

**Prerequisites**: Have existing memory records for an actor

**Steps**:
1. Set actor ID to one with existing memories
2. Send any message
3. Observe the response

**Expected Results**:
- [ ] Response reflects knowledge from memory
- [ ] Assistant doesn't ask for information it already has
- [ ] Personalization is evident in responses

---

### TC-MEM-031: Memory Context Format Verification

**Objective**: Verify memory context is properly formatted

**Steps**:
1. Add debug logging to format_memory_context function (temporary)
2. Retrieve memory for an actor with records
3. Check the formatted context

**Expected Results**:
- [ ] Context includes "## Memory Context" header
- [ ] User preferences prefixed with "User Preference:"
- [ ] Known facts prefixed with "Known Fact:"
- [ ] Session summaries prefixed with "Previous Session:"

---

## Test Suite 5: Error Handling

### TC-MEM-040: Handle Memory API Errors Gracefully

**Objective**: Verify app continues working when memory API fails

**Steps**:
1. Temporarily use invalid memory ID (modify AGENTCORE_MEMORY_ID)
2. Send a message
3. Observe behavior

**Expected Results**:
- [ ] Conversation still works
- [ ] Error is logged in "Memory Errors" expander
- [ ] User experience is not blocked

---

### TC-MEM-041: Handle Invalid Namespace Gracefully

**Objective**: Verify retrieval handles non-existent namespaces

**Steps**:
1. Set actor ID to a new, never-used value like "brand-new-user-xyz"
2. Send a message

**Expected Results**:
- [ ] No errors displayed to user
- [ ] Memory record count shows 0
- [ ] Conversation works normally

---

### TC-MEM-042: Clear Memory Cache Button

**Objective**: Verify clear memory cache resets local state

**Steps**:
1. Have a conversation to populate memory records
2. Verify memory record count > 0
3. Click "Clear Memory Cache" button

**Expected Results**:
- [ ] Page reloads
- [ ] Memory record count shows 0 or "No memory records yet"
- [ ] Memory errors are cleared
- [ ] Note: This only clears local cache, not server-side memories

---

## Test Suite 6: Actor ID Management

### TC-MEM-050: Change Actor ID Mid-Session

**Objective**: Verify changing actor ID switches memory context

**Steps**:
1. Set actor ID to "user-one"
2. Send message: "My favorite color is blue"
3. Change actor ID to "user-two"
4. Verify memory records reset to 0
5. Send message: "What's my favorite color?"

**Expected Results**:
- [ ] Memory records clear when actor ID changes
- [ ] New actor doesn't have access to previous actor's memories
- [ ] Assistant doesn't know user-two's favorite color

---

### TC-MEM-051: Actor ID Validation

**Objective**: Verify actor ID follows naming constraints

**Steps**:
1. Try setting actor ID with special characters: "user@test!"
2. Try setting actor ID with spaces: "user with spaces"
3. Try valid actor ID: "user_test_123"

**Expected Results**:
- [ ] Invalid characters may cause API errors
- [ ] Valid alphanumeric with underscores works
- [ ] Errors are captured and displayed

---

## Test Suite 7: Integration with Ticket System

### TC-MEM-060: Remember Ticket Preferences

**Objective**: Verify memory helps with ticket management

**Steps**:
1. Set actor ID to "ticket-user"
2. Send: "I usually deal with Network category tickets"
3. Wait for response
4. Send: "Create a ticket for VPN issues"
5. Observe the ticket category suggestion

**Expected Results**:
- [ ] Assistant may suggest "Network" category based on preference
- [ ] Ticket creation reflects user preferences when applicable

---

### TC-MEM-061: Remember Previous Ticket Discussions

**Objective**: Verify memory retains ticket context

**Steps**:
1. Create a ticket about a specific issue
2. Note the ticket ID
3. Clear chat (but not memory)
4. Ask: "What was the last ticket I created?"

**Expected Results**:
- [ ] If memory extraction ran, assistant recalls ticket details
- [ ] Context from previous session is available

---

## Verification Commands Reference

```bash
# List all events for an actor
AWS_PROFILE=kcom aws bedrock-agentcore list-events \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --actor-id <actor-id>

# List memory records in a namespace
AWS_PROFILE=kcom aws bedrock-agentcore list-memory-records \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --namespace "<namespace>"

# Get a specific memory record
AWS_PROFILE=kcom aws bedrock-agentcore get-memory-record \
  --memory-id msp_support_assistant_memory-NeCST586bk \
  --memory-record-id <record-id>

# Get memory resource info
AWS_PROFILE=kcom aws bedrock-agentcore-control get-memory \
  --memory-id msp_support_assistant_memory-NeCST586bk
```

---

## Test Suite 8: Strands Agent Features

### TC-STR-001: Verify @tool Decorated Functions

**Objective**: Confirm all Strands tools are loaded and functional

**Steps**:
1. Open the Strands app
2. Check sidebar "SDK Status" for tool count
3. Ask "What tools do you have available?"

**Expected Results**:
- [ ] Shows "Tools: 6 loaded"
- [ ] Agent describes available tools (list_tickets, create_ticket, etc.)

---

### TC-STR-002: Test Tool Execution via Agent

**Objective**: Verify Strands Agent can execute tools

**Steps**:
1. Open the Strands app
2. Send message: "Show me all tickets"
3. Observe "Tool Executions" section

**Expected Results**:
- [ ] Agent uses `list_tickets` tool
- [ ] Tool execution shows in sidebar with input parameters
- [ ] Agent returns formatted ticket list

---

### TC-STR-003: Test Agentic RAG (retrieve_memories)

**Objective**: Verify the retrieve_memories tool for proactive memory search

**Prerequisites**: Have existing memory records for an actor

**Steps**:
1. Set actor ID to one with existing memories
2. Send message: "Search your memory for information about my preferences"

**Expected Results**:
- [ ] Agent may use `retrieve_memories` tool
- [ ] Agent provides personalized response based on memory

---

### TC-STR-004: Test Agent Reset

**Objective**: Verify Reset Agent button recreates agent with new session

**Steps**:
1. Have a conversation with the agent
2. Click "Reset Agent" button in sidebar
3. Verify session ID changed
4. Send a new message

**Expected Results**:
- [ ] Page reloads
- [ ] New session ID generated
- [ ] Agent still functional with new session

---

### TC-STR-005: Test BedrockModel Configuration

**Objective**: Verify Amazon Nova Pro is configured correctly

**Steps**:
1. Open the Strands app
2. Send a complex query requiring reasoning
3. Observe response quality

**Expected Results**:
- [ ] Response is coherent and well-formatted
- [ ] Agent uses tools appropriately
- [ ] No model configuration errors

---

## Notes

1. **Extraction Timing**: Long-term memory extraction is not instant. Allow 5-10 minutes for strategies to process events.

2. **Event Expiry**: Events expire after 30 days (configured in Terraform).

3. **Memory Strategies**:
   - `user_preferences` - Extracts preference-like statements
   - `semantic_facts` - Extracts factual information
   - `session_summaries` - Creates conversation summaries

4. **Namespace Patterns**:
   - Preferences: `/preferences/{actorId}`
   - Facts: `/facts/{actorId}`
   - Summaries: `/summaries/{actorId}/{sessionId}`

5. **Strands SDK Components**:
   - `Agent` - Main agent class with tool orchestration
   - `BedrockModel` - Amazon Bedrock model provider
   - `@tool` - Decorator for creating tool functions
   - `AgentCoreMemorySessionManager` - Memory integration

6. **Available Tools**:
   - `list_tickets` - List/filter tickets
   - `create_ticket` - Create new tickets
   - `get_ticket` - Get ticket details
   - `update_ticket` - Update tickets
   - `get_ticket_summary` - Get statistics
   - `retrieve_memories` - Agentic RAG

---

## Test Execution Log

### Memory Test Cases
| Test Case | Date | Tester | Status | Notes |
|-----------|------|--------|--------|-------|
| TC-MEM-001 | | | | |
| TC-MEM-002 | | | | |
| TC-MEM-010 | | | | |
| TC-MEM-011 | | | | |
| TC-MEM-012 | | | | |
| TC-MEM-013 | | | | |
| TC-MEM-020 | | | | |
| TC-MEM-021 | | | | |
| TC-MEM-022 | | | | |
| TC-MEM-023 | | | | |
| TC-MEM-030 | | | | |
| TC-MEM-031 | | | | |
| TC-MEM-040 | | | | |
| TC-MEM-041 | | | | |
| TC-MEM-042 | | | | |
| TC-MEM-050 | | | | |
| TC-MEM-051 | | | | |
| TC-MEM-060 | | | | |
| TC-MEM-061 | | | | |

### Strands Agent Test Cases
| Test Case | Date | Tester | Status | Notes |
|-----------|------|--------|--------|-------|
| TC-STR-001 | | | | |
| TC-STR-002 | | | | |
| TC-STR-003 | | | | |
| TC-STR-004 | | | | |
| TC-STR-005 | | | | |
