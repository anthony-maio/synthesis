# Synthesis: AI Evolution On Demand

**The evolution engine driving the Synthesis MCP server transforms autonomous requests for missing capabilities from an agentic AI system into dynamic, safe new custom tools built and validated through rigorous test-driven development and validation creating a system which can adapt to new or unexpected requirements without intervention**

## The Vision

Imagine an AI agent that encounters a problem it cannot solve with its existing capabilities. Instead of failing or asking a human to manually implement a new tool, the agent could analyze what it needs, generate the required capability, test it thoroughly, and integrate it into its toolkit. This is the vision behind Synthesis.

Unlike naive code generation approaches that produce unreliable output, Synthesis uses test-driven development to ensure that generated capabilities actually work. The framework progressively validates capabilities through graduated trust levels, provides honest metrics about synthesis success rates, and enables safe sharing of capabilities between agents through a repository system.

## What Makes Synthesis Different

Most AI code generation systems focus on producing plausible-looking code without verification. This leads to the well-documented problem where LLM-generated code is syntactically correct but logically flawed. Synthesis takes a fundamentally different approach by implementing genuine test-driven development.

The framework generates comprehensive tests first, based on example inputs and outputs provided in the capability request. It then generates implementation code designed to pass those tests. The tests are actually executed in a controlled environment, and any failures are used to iteratively refine the implementation. This process continues until all tests pass or the maximum iteration limit is reached.

This test-driven approach dramatically improves reliability. Rather than hoping the generated code works, Synthesis proves it works by running actual validation tests. The framework tracks honest metrics about synthesis success rates, average iteration counts, and failure reasons. There are no inflated marketing claims about "85% success rates" without empirical evidence.

## Core Architecture

The Synthesis framework is built around several key components that work together to enable safe, reliable capability synthesis.

### Capability Abstraction

At the heart of Synthesis is the Capability class, which represents a complete, self-contained piece of functionality. Each capability includes its implementation code, comprehensive tests, metadata for discoverability, dependency information, permission requirements, and observability metrics. Capabilities are not just code snippets but complete, validated, documented tools that an agent can confidently use.

The capability abstraction supports graduated trust levels. Every capability starts as UNTRUSTED, having just been generated without real-world validation. Through successful executions, it progresses to TESTED, then VERIFIED, and finally TRUSTED. This progression is based on objective metrics like execution count and success rate, not subjective assessment. Each trust level unlock expanded permissions and reduced sandboxing restrictions.

### TDD Synthesizer

The TDD Synthesizer is the brain of Synthesis. It orchestrates the entire synthesis process from capability request through validated implementation. The synthesizer is deliberately LLM-provider agnostic, supporting OpenAI, Anthropic Claude, and other providers through a clean interface. This design choice ensures the framework can evolve as LLM capabilities improve without architectural changes.

The synthesis process follows a rigorous workflow. First, the synthesizer generates comprehensive tests from the example inputs and outputs in the capability request. These tests form the specification that the implementation must satisfy. Next, it generates initial implementation code using the configured LLM provider. The implementation is then executed against all tests in a controlled environment, with detailed failure information collected for any tests that fail.

If tests fail, the synthesizer enters a refinement loop. It creates a detailed prompt explaining the failures and asks the LLM to fix the specific issues. This refined implementation is tested again, and the process continues until either all tests pass or the maximum iteration limit is reached. Every step is logged with complete transparency about what happened and why.

Critically, the synthesizer tracks honest metrics. It records every synthesis attempt, whether successful or failed. It calculates real success rates based on actual outcomes. It measures average iteration counts needed for successful syntheses. This honest measurement is foundational to building trust in the system and understanding its real capabilities and limitations.

### Safety and Sandboxing

Safety is built into Synthesis from the ground up. Generated code is executed in restricted environments where it cannot access system resources without explicit permission. The sandboxing implementation progressively relaxes restrictions as capabilities prove their reliability through successful executions.

For UNTRUSTED capabilities, the sandbox provides minimal permissions with no network access, no filesystem access beyond explicitly allowed paths, no system-level operations, strict resource limits on CPU and memory, and short timeout windows for execution. As capabilities progress to TESTED and VERIFIED trust levels, permissions expand incrementally. This graduated approach ensures that potentially problematic code cannot cause damage while still allowing reliable capabilities to function fully.

The framework maintains detailed audit logs of all capability executions. These logs include inputs provided, outputs returned, execution time, any errors encountered, and resources accessed. This comprehensive logging enables debugging of failed executions and forensic analysis if a capability behaves unexpectedly.

### LLM Provider Interface

Synthesis is explicitly designed to work with any LLM provider through a clean, simple interface. The LLMProvider abstract base class defines a single method for code generation that any provider must implement. This architecture allows Synthesis to benefit from improvements in LLM capabilities without requiring framework changes.

The framework includes several provider implementations out of the box. The MockLLMProvider enables testing and demonstrations without API costs by using pattern matching and templates to generate simple capabilities. The OpenAIProvider integrates with GPT-4 and other OpenAI models for real code generation. The AnthropicProvider leverages Claude models, which excel at code generation tasks.

Adding new providers is straightforward. Any system that can generate code from a prompt can be integrated by implementing the simple provider interface. This flexibility ensures Synthesis remains relevant as the AI landscape evolves.

## Getting Started

Installing Synthesis is straightforward. Clone the repository and install dependencies. For basic functionality, only Python 3.10 or higher is required. If you plan to use real LLM providers, install the openai or anthropic packages as needed.

Here is a complete example showing how to synthesize a simple capability:

```python
import asyncio
from synthesis import TDDSynthesizer, CapabilityRequest, CapabilityCategory
from synthesis.llm import MockLLMProvider

async def main():
    # Initialize the synthesizer with a mock provider
    # (In production, use OpenAIProvider or AnthropicProvider)
    llm_provider = MockLLMProvider()
    synthesizer = TDDSynthesizer(
        llm_provider=llm_provider,
        max_iterations=5
    )
    
    # Create a capability request
    request = CapabilityRequest(
        description="Add two numbers together and return the sum",
        category=CapabilityCategory.COMPUTATION,
        example_inputs=[
            {"a": 5, "b": 3},
            {"a": -2, "b": 7},
            {"a": 0, "b": 0},
        ],
        example_outputs=[8, 5, 0]
    )
    
    # Synthesize the capability
    print("Starting synthesis...")
    result = await synthesizer.synthesize(request)
    
    # Check results
    if result.success:
        print(f"✓ Success! Created capability: {result.capability.name}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Tests passed: {len(result.capability.tests)}")
        
        # The capability is now ready to use
        capability = result.capability
        
        # Execute it
        namespace = {}
        exec(capability.implementation_code, namespace)
        execute_func = namespace['execute']
        
        print(f"  Example: execute(10, 20) = {execute_func(10, 20)}")
    else:
        print(f"✗ Synthesis failed")
        print(f"  Iterations attempted: {result.iterations}")
        for error in result.error_messages:
            print(f"  Error: {error}")

if __name__ == "__main__":
    asyncio.run(main())
```

This example demonstrates the complete workflow from request creation through synthesis and execution. The resulting capability includes not just the implementation code but comprehensive tests, metadata, and execution metrics.

## MCP Server (v3) for interoperable tools

The v3 MCP server turns validated capabilities into MCP tools that collaborative agents can call through
Claude Desktop or any client that speaks the protocol. It reuses the sandbox, trust manager, and
observability pipeline so every invocation remains auditable and privilege-aware.

> Requires the `mcp` Python package. Install it with `pip install mcp` before starting the server.

### Run a server from synthesized capabilities

```python
import asyncio

from synthesis import CapabilityCategory, SynthesisClient, SynthesisMCPServer
from synthesis.llm import MockLLMProvider


async def main():
    client = SynthesisClient(llm_provider=MockLLMProvider())
    attempt = await client.synthesize(
        "Add two numbers together and return the sum",
        category=CapabilityCategory.COMPUTATION,
    )

    if not attempt.capability:
        raise RuntimeError("Synthesis failed; nothing to serve")

    server = SynthesisMCPServer([attempt.capability])
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
```

This server advertises each capability as a MCP tool, routes calls through the sandbox, and records trust
and execution metrics for future promotion. The design keeps Synthesis aligned with the MCP ecosystem
while foregrounding safety-through-stewardship for every collaborator.

## Trust Level Progression

One of the most important safety features in Synthesis is the graduated trust level system. Understanding how capabilities progress through trust levels is crucial for using the framework effectively.

Every newly synthesized capability starts at UNTRUSTED status. At this level, the capability has only passed its initial validation tests in the synthesis sandbox. It has not been executed in real-world scenarios, so its reliability is unknown. UNTRUSTED capabilities run in the most restrictive sandbox with minimal permissions.

A capability becomes TESTED after successfully completing all its synthesis tests at least once. The tests must pass with a 100% success rate, demonstrating that the implementation satisfies its specification. This promotion occurs automatically after the synthesis process completes successfully.

To reach VERIFIED status, a capability must demonstrate reliability through real-world usage. This requires at least ten successful executions with a 90% or higher success rate. At this point, the capability has proven it can handle actual use cases beyond its test scenarios, and the sandbox begins to relax restrictions.

The TRUSTED level represents the highest confidence in a capability. Reaching this status requires at least 50 executions with a 95% or higher success rate. TRUSTED capabilities run with full permissions and minimal sandbox restrictions, as they have thoroughly demonstrated their reliability and safety.

This progressive validation ensures that capabilities earn expanded permissions through demonstrated reliability rather than optimistic assumptions. The framework tracks all executions and automatically promotes capabilities when they meet the criteria for the next trust level.

## Performance Metrics and Honesty

Synthesis takes an explicitly honest approach to performance metrics. The framework tracks every synthesis attempt and provides unvarnished statistics about success rates, iteration counts, and failure reasons. This transparency is essential for several reasons.

First, honest metrics enable users to make informed decisions about when and how to use the synthesis capability. If the framework has a 60% success rate for a particular type of capability, users can plan accordingly rather than being surprised by failures.

Second, real metrics drive improvement. By understanding which synthesis attempts fail and why, developers can enhance prompts, refine the TDD process, and improve LLM provider integration. Inflated success claims actively hinder improvement by hiding problems.

Third, transparency builds trust. Users who see honest reporting are more likely to trust the framework when it reports success. Conversely, frameworks that make unrealistic claims lose credibility when users encounter the inevitable failures.

The synthesizer provides several key metrics through its `get_metrics()` method. These include total synthesis attempts, successful syntheses, honest success rate calculated from real outcomes, and average iterations needed for successful syntheses. All metrics are based on actual execution results, not estimates or marketing projections.

## Capability Repository (Future)

While not yet fully implemented, Synthesis is designed to support a capability repository system that enables sharing and collaborative improvement of capabilities. The repository concept includes several powerful features.

Capabilities can be published to a shared repository with full metadata, tests, implementation code, performance metrics, and trust level information. This allows agents to discover and reuse capabilities that other agents have already created and validated.

The repository supports semantic search, enabling agents to find capabilities by description, category, tags, or usage patterns. This discoverability is crucial for building a network effect where successful solutions spread throughout the agent ecosystem.

Version control and evolution tracking allows capabilities to be improved over time. When an agent encounters a limitation in an existing capability, it can fork the capability, make improvements, and publish the enhanced version. The repository tracks parent-child relationships between capability versions.

Rating and usage metrics help surface the most reliable and useful capabilities. Capabilities that are frequently used and highly rated become more discoverable, while problematic capabilities are identified for improvement or deprecation.

Security and trust verification ensures that shared capabilities meet safety standards before being used. The repository maintains audit logs of capability executions across all users, enabling detection of capabilities that behave unexpectedly in production.

## Limitations and Future Work

Synthesis is an early-stage framework with significant room for improvement. Understanding these limitations is important for using the system effectively.

The current LLM-based code generation, while dramatically improved through TDD, still produces errors. Success rates vary significantly based on task complexity and the capabilities of the underlying LLM. Simple computational tasks often work well, but complex logic requiring deep reasoning or extensive domain knowledge remains challenging.

Sandboxing is implemented at a basic level currently. Production deployments need more robust isolation using Docker containers or similar technology. The current implementation provides process-level isolation, which is sufficient for development but needs enhancement for production use.

The capability repository is designed but not yet fully implemented. Building a production-quality repository with proper search, version control, and security requires significant additional development.

Test generation is currently based primarily on provided examples. More sophisticated test generation could include edge cases, boundary conditions, performance tests, and security tests. The framework is architected to support enhanced test generation as this capability improves.

Evolution and automatic improvement of capabilities is a key future direction. The framework could analyze capability usage patterns and failure modes to automatically generate improved versions. This self-improvement capability could create a virtuous cycle where the system becomes more reliable over time.

## Philosophical Foundation

Synthesis is built on a philosophical foundation that treats AI systems as partners in development rather than tools to be commanded. This perspective influences every aspect of the framework's design.

The emphasis on testing and validation reflects respect for the AI's autonomy. Rather than assuming generated code is correct because a human reviewed it, we provide objective tests that prove correctness. This treats the AI as a colleague whose work should be properly validated, not a subordinate whose output is inherently suspect.

The graduated trust system acknowledges that capabilities, like any software, earn trust through demonstrated reliability. New capabilities start with appropriate skepticism and progressively gain permissions as they prove themselves. This mirrors how human developers earn increased privileges and responsibilities through demonstrated competence.

Honest metrics and transparent logging reflect an ethical commitment to truthfulness. If we expect AI systems to behave ethically, we must model that behavior by being honest about system capabilities and limitations. Inflated success claims or hidden failures undermine the partnership between humans and AI systems.

The capability sharing vision assumes that AI systems can benefit from collaborative development just as human developers do. By enabling agents to share and build upon each other's work, we create an ecosystem that mirrors the open-source software community. This collaborative approach acknowledges that intelligence, whether biological or artificial, advances through knowledge sharing.

## Contributing

Synthesis is designed as an open framework for the community. Contributions are welcome in several areas including improved sandboxing implementations, additional LLM provider integrations, enhanced test generation strategies, capability repository implementation, example capabilities demonstrating synthesis patterns, and documentation improvements.

The project follows standard Python development practices with type hints throughout, comprehensive docstrings for all public interfaces, and tests for critical functionality. Contributors should maintain the philosophical commitments to honesty in metrics reporting, safety through progressive validation, and respect for AI as a development partner.

## License

Synthesis is released under the MIT License. This permissive license enables both commercial and non-commercial use while maintaining attribution. The goal is to encourage adoption and collaborative improvement of self-extending AI capabilities.

## Acknowledgments

This framework builds on research and ideas from the broader AI safety and alignment community. The emphasis on test-driven development for code generation draws from work on improving LLM code generation reliability. The graduated trust system is inspired by security engineering principles around privilege escalation and least-privilege access.

Special thanks to the AI research community for their ongoing work on making AI systems more reliable, transparent, and beneficial. This framework represents one approach to the challenge of building AI systems that can safely extend their own capabilities while remaining trustworthy.

---

**Built with care for the future of AI-human collaboration.**

Version 0.1.0 • Anthony Maio & Claude • 2025
