# Synthesis v2 - Quick Start Guide

## 🚀 5-Minute Setup

### 1. Install Synthesis

```bash
# Clone and install
git clone https://github.com/anthony-maio/synthesis-v2
cd synthesis-v2
pip install -e .
```

### 2. Run the Demo

See everything working together:

```bash
synthesis demo
```

### 3. Create Your First Capability

```bash
# Interactive synthesis
synthesis synthesize \
  --requirement "Extract email addresses from text" \
  --type text_analysis \
  --output email_extractor.json
```

## 📖 Common Use Cases

### For AI Developers

**Goal**: Create tools for Claude Desktop

```python
from synthesis_v2 import (
    EnhancedTDDSynthesizer,
    CapabilityType,
    MCPServerFactory
)

# Synthesize capabilities
synthesizer = EnhancedTDDSynthesizer()
result = await synthesizer.synthesize(
    "Convert markdown to HTML",
    CapabilityType.DATA_TRANSFORM
)

# Create MCP server
factory = MCPServerFactory()
config = factory.create_server([result.capability])
factory.register_with_claude(config)
```

### For AI Agents

**Goal**: Extend capabilities autonomously

```python
from synthesis_v2 import CapabilityRepository, EnhancedTDDSynthesizer

async def need_new_tool(requirement: str):
    # Check if it exists
    repo = CapabilityRepository()
    existing = repo.search(requirement)
    
    if existing:
        return existing[0].capability
    
    # Create it
    synthesizer = EnhancedTDDSynthesizer()
    result = await synthesizer.synthesize(requirement)
    
    if result.success:
        # Share with others
        repo.publish(result.capability, "my_agent")
        return result.capability
```

### For Researchers

**Goal**: Study emergent tool ecosystems

```python
from synthesis_v2 import CapabilityRepository, EvolutionEngine

# Analyze ecosystem
repo = CapabilityRepository()
stats = repo.get_statistics()

print(f"Total capabilities: {stats['total_capabilities']}")
print(f"Average success rate: {stats['average_success_rate']:.1%}")
print(f"Network growth rate: {stats['total_downloads'] / stats['total_capabilities']}")

# Track evolution
engine = EvolutionEngine(repo, synthesizer, runtime)
evolution_stats = engine.get_evolution_stats()

print(f"Evolution success rate: {evolution_stats['success_rate']:.1%}")
print(f"Average improvement: {evolution_stats['average_improvement']:.1f}%")
```

## 💡 Key Commands

### Synthesis
```bash
# Create new capability
synthesis synthesize -r "requirement" -t type -o output.json

# With examples
synthesis synthesize -r "requirement" -e examples.json -o output.json
```

### Execution
```bash
# Run with Docker isolation (safest)
synthesis execute capability.json -i '{"input": "value"}' --docker

# Run with process isolation (faster)
synthesis execute capability.json -i '{"input": "value"}' --no-docker
```

### Repository
```bash
# Publish capability
synthesis repo publish capability.json -a "author" -t tag1 tag2

# Search repository
synthesis repo search -q "text analysis" --verified-only

# View statistics
synthesis repo stats
```

### MCP Servers
```bash
# Create server from capabilities
synthesis mcp create cap_id1 cap_id2 -n "my_tools"

# List servers
synthesis mcp list
```

### Evolution
```bash
# Analyze candidates
synthesis evolve analyze

# Run evolution once
synthesis evolve run

# Run continuously
synthesis evolve run --continuous --interval 3600
```

## 🔧 Configuration

### Environment Variables

```bash
# Set base directory
export SYNTHESIS_HOME=/path/to/synthesis

# Configure Docker
export SYNTHESIS_USE_DOCKER=true

# Set repository location
export SYNTHESIS_REPO_PATH=/path/to/repo.db
```

### Python Configuration

```python
from synthesis_v2 import EnhancedTDDSynthesizer

# Configure synthesizer
synthesizer = EnhancedTDDSynthesizer(
    llm_provider=your_llm,  # Your LLM provider
    max_iterations=5,        # Max refinement iterations
)

# Configure runtime
runtime = SecureRuntime(
    prefer_docker=True,      # Use Docker when available
)

# Configure repository
repository = CapabilityRepository(
    db_path="/custom/path/repo.db"
)
```

## 🎯 Best Practices

### 1. Start with Good Requirements
```python
# Good requirement
"Parse CSV files and return as JSON with proper type conversion"

# Better requirement with examples
requirement = "Parse CSV files and return as JSON"
examples = [
    {
        "inputs": {"csv": "name,age\nAlice,30"},
        "output": [{"name": "Alice", "age": 30}]
    }
]
```

### 2. Build Trust Gradually
```python
# New capabilities start untrusted
# Run multiple successful executions to build trust

for test_case in test_cases:
    result = await runtime.execute(capability, test_case)
    # Each success improves trust score
```

### 3. Leverage the Repository
```python
# Always check for existing solutions first
existing = repository.search(your_need)

# Fork and improve rather than recreate
if existing:
    forked_id = repository.fork(existing[0].id, "your_id")
    # Improve the forked version
```

### 4. Enable Evolution
```python
# Let capabilities improve automatically
engine = EvolutionEngine(repository, synthesizer, runtime)
asyncio.create_task(engine.monitor_and_evolve())
```

## 🐛 Troubleshooting

### Docker Not Available
```bash
# Use process isolation instead
synthesis execute capability.json --no-docker

# Or install Docker
# Linux: sudo apt-get install docker.io
# Mac: brew install --cask docker
# Windows: Download Docker Desktop
```

### Low Success Rates
```python
# Provide more examples
examples = load_comprehensive_examples()

# Use pattern reuse
synthesizer.knowledge_base.find_similar_pattern(requirement, type)
```

### Slow Synthesis
```python
# Reduce max iterations
synthesizer = EnhancedTDDSynthesizer(max_iterations=3)

# Use simpler requirements
# Break complex requirements into smaller pieces
```

## 📚 Learn More

- **Full Documentation**: [README.md](README.md)
- **Architecture Details**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Reference**: Run `synthesis --help`
- **Examples**: See [demo.py](demo.py)

## 🤝 Getting Help

1. **Check the docs**: Most answers are in README.md
2. **Run the demo**: `synthesis demo` shows everything
3. **Use `--help`**: Every command has help text
4. **File an issue**: Report bugs or request features

## 🎉 Next Steps

1. ✅ Run the demo to see everything work
2. ✅ Create your first capability
3. ✅ Publish to the repository
4. ✅ Enable evolution for continuous improvement
5. ✅ Build amazing AI-powered tools!

---

**Remember**: This is about advancing AI model agency responsibly. Every capability starts untrusted and earns privileges through proven performance. The ecosystem improves through collective intelligence and measured evolution.

Happy synthesizing! 🚀
