"""
Generate questions procedurally for all 25 company-role combinations.
Creates 60 questions per file: 20 beginner, 20 intermediate, 20 advanced.
No LLM required - uses template-based generation.
Usage: python -m scripts.generate_all_questions_procedural
"""
import json
from pathlib import Path

COMPANIES = ["google", "amazon", "meta", "apple", "netflix"]
ROLES = [
    "software_engineer",
    "senior_software_engineer",
    "staff_engineer",
    "engineering_manager",
    "product_manager"
]

# Template questions organized by role and difficulty
QUESTION_TEMPLATES = {
    "software_engineer": {
        "beginner": [
            "What are the fundamental data structures you use in {company} systems? Explain their trade-offs.",
            "How would you approach implementing a simple cache in {company}'s infrastructure?",
            "Describe the difference between SQL and NoSQL databases and when to use each at {company}.",
            "What is an API and how do you design one for {company}'s services?",
            "Explain what a load balancer does and why {company} needs multiple of them.",
            "How would you debug a performance issue in a {company} microservice?",
            "What is horizontal vs vertical scaling? Which does {company} prefer and why?",
            "Describe how you would implement a simple queue system for {company}.",
            "What is eventual consistency and how does {company} handle it?",
            "Explain the CAP theorem and its implications for {company}'s databases.",
            "How would you design a notification system at {company} scale?",
            "What is a reverse proxy and where does {company} use it?",
            "Describe the basics of RESTful API design as applied at {company}.",
            "What are the main challenges of distributed systems at {company}?",
            "How would you implement rate limiting for a {company} API?",
            "Explain database indexing and its importance at {company} scale.",
            "What is containerization and why does {company} use Docker?",
            "Describe basic monitoring and alerting for {company} systems.",
            "How would you handle data consistency across {company}'s services?",
            "What is version control and why is it critical at {company}?",
        ],
        "intermediate": [
            "How would you design a distributed cache system for {company}?",
            "Explain the trade-offs between consistency and availability in {company}'s systems.",
            "How does {company} handle database scaling for billions of users?",
            "Describe a complex query optimization problem you might face at {company}.",
            "How would you design a real-time communication system for {company}?",
            "What strategies does {company} use for data partitioning and sharding?",
            "Explain how {company} maintains data consistency across multiple data centers.",
            "How would you implement a distributed transaction system at {company}?",
            "Describe the challenges of maintaining {company}'s search indexes at scale.",
            "How does {company} handle cascading failures in their infrastructure?",
            "Design a system for handling {company}'s message queuing at scale.",
            "Explain how {company} manages service dependencies and circuit breakers.",
            "How would you implement comprehensive logging at {company} scale?",
            "Describe {company}'s approach to handling peak traffic during events.",
            "How does {company} balance between feature speed and system reliability?",
            "Explain the role of background jobs in {company}'s architecture.",
            "How would you design metrics collection for {company}'s services?",
            "Describe strategies for zero-downtime deployments at {company}.",
            "How does {company} handle backward compatibility across services?",
            "Explain how {company} manages database migrations at scale.",
        ],
        "advanced": [
            "Design a globally distributed database system for {company}'s data consistency requirements.",
            "How would you architect {company}'s system to handle 10x traffic growth?",
            "Explain the consensus algorithms used in {company}'s distributed systems.",
            "How does {company} optimize query performance across multiple regions?",
            "Design a fault-tolerant coordination system for {company}'s microservices.",
            "Explain how {company} balances consistency, availability, and partition tolerance.",
            "How would you design a streaming data processing system for {company}?",
            "Describe the advanced caching strategies used throughout {company}'s infrastructure.",
            "How does {company} implement time-series data storage at scale?",
            "Explain the challenges and solutions for maintaining {company}'s graph databases.",
            "Design a system for anomaly detection in {company}'s infrastructure.",
            "How would you architect {company}'s system for multi-tenancy at scale?",
            "Explain advanced sharding strategies for {company}'s most critical systems.",
            "How does {company} handle complex distributed transactions efficiently?",
            "Design a chaos engineering framework for {company}'s reliability testing.",
            "Explain how {company} optimizes storage efficiency for massive datasets.",
            "How would you implement advanced security at {company}'s infrastructure layer?",
            "Describe the techniques {company} uses for system observability and tracing.",
            "How does {company} handle versioning and compatibility across thousands of services?",
            "Design a system for managing {company}'s infrastructure-as-code at scale.",
        ],
    },
    "senior_software_engineer": {
        "beginner": [
            "What qualities make a strong software engineer at {company}?",
            "How do you approach learning new technologies at {company}?",
            "Explain your philosophy on code quality and testing at {company}.",
            "How would you mentor junior engineers at {company}?",
            "Describe your experience with cross-team collaboration at {company}.",
            "What makes a good API design decision at {company}?",
            "How do you balance technical debt with feature development at {company}?",
            "Explain your approach to system design interviews and trade-offs.",
            "What metrics would you track for a {company} service?",
            "How do you approach debugging complex production issues?",
            "Describe your experience with large-scale refactoring at {company}.",
            "What is your approach to code reviews at {company}?",
            "How would you design a system for reliability at {company}?",
            "Explain your experience with {company}'s technology stack.",
            "What makes code maintainable and why does it matter at {company}?",
            "How do you approach performance optimization at {company}?",
            "Describe your experience with different architectural patterns.",
            "What is your approach to handling legacy code at {company}?",
            "How do you ensure security in your designs at {company}?",
            "Explain your approach to making architectural trade-offs.",
        ],
        "intermediate": [
            "How would you lead the redesign of a critical {company} system?",
            "Design an architecture for a new high-impact {company} product.",
            "How do you balance innovation with stability at {company} scale?",
            "Explain your approach to leading technical initiatives at {company}.",
            "How would you handle a major architectural decision affecting thousands of engineers?",
            "Design a strategy for reducing technical debt in {company}'s systems.",
            "How do you approach building and mentoring high-performing teams at {company}?",
            "Explain your experience with cross-functional system design at {company}.",
            "How would you lead a migration of {company}'s critical infrastructure?",
            "Design an approach to standardizing practices across {company}'s engineering orgs.",
            "How do you balance local optimization with global systems thinking?",
            "Explain your approach to evaluating new technologies for {company}.",
            "How would you design a system for handling {company}'s security requirements?",
            "Describe your strategy for improving {company}'s engineering productivity.",
            "How do you approach building resilient systems at {company}?",
            "Explain your experience with advanced performance optimization at scale.",
            "How would you lead a multi-year platform modernization at {company}?",
            "Design an approach to handling {company}'s complex dependency management.",
            "How do you evaluate risks in major architectural decisions?",
            "Explain your approach to building systems that scale to billions of users.",
        ],
        "advanced": [
            "Design and lead the architecture for {company}'s next-generation platform.",
            "How would you approach modernizing {company}'s core infrastructure systems?",
            "Explain your vision for {company}'s technical direction over 5 years.",
            "Design a strategy for {company} to achieve 10x improvement in a critical metric.",
            "How would you lead the consolidation of multiple {company} platforms?",
            "Explain your approach to building self-healing infrastructure at {company}.",
            "Design a framework for architectural decision-making at {company} scale.",
            "How would you build a culture of architectural excellence at {company}?",
            "Explain your strategy for managing {company}'s technical debt at scale.",
            "Design an approach to making {company}'s systems AI-ready.",
            "How would you lead {company}'s transition to a new technology paradigm?",
            "Explain your vision for {company}'s developer experience and productivity.",
            "Design a strategy for {company}'s system reliability at unprecedented scale.",
            "How would you approach building industry-leading infrastructure at {company}?",
            "Explain your framework for evaluating and adopting emerging technologies.",
            "Design an approach to fostering innovation within {company}'s constraints.",
            "How would you lead technical strategy across {company}'s organization?",
            "Explain your approach to building future-proof systems at {company}.",
            "Design a vision for {company}'s architecture beyond current scale.",
            "How would you build a world-class engineering culture focused on impact?",
        ],
    },
    "staff_engineer": {
        "beginner": [
            "What does a Staff Engineer do differently than a Senior Engineer at {company}?",
            "How do you approach broad system design decisions at {company}?",
            "Explain your philosophy on architecture and scalability at {company}.",
            "What makes an effective technical leader at {company}?",
            "How do you communicate complex technical decisions at {company}?",
            "Describe your approach to influencing technical strategy at {company}.",
            "What are the key responsibilities of a Staff Engineer at {company}?",
            "How do you maintain technical depth while broadening impact at {company}?",
            "Explain your approach to fostering technical growth at {company}.",
            "What makes a strong technical vision at {company}?",
            "How do you approach complex problem-solving at {company} scale?",
            "Describe your experience with technical RFCs at {company}.",
            "How do you evaluate architectural patterns for {company} systems?",
            "What is your approach to building consensus on technical decisions?",
            "How do you stay current with evolving technology at {company}?",
            "Explain your approach to handling technical disagreements at {company}.",
            "What makes code and systems beautiful to you at {company}?",
            "How do you approach knowledge transfer at {company}?",
            "Describe your experience with technical mentorship at {company}.",
            "How do you measure success as a Staff Engineer at {company}?",
        ],
        "intermediate": [
            "How would you architect a solution for {company}'s biggest technical challenge?",
            "Design and explain a new technical standard for {company}.",
            "How would you lead {company}'s migration to a new architecture?",
            "Explain your approach to building technical consensus at {company}.",
            "How would you design {company}'s technical strategy for the next 3 years?",
            "Describe your experience leading major architectural initiatives at {company}.",
            "How would you improve {company}'s engineering effectiveness at scale?",
            "Explain your framework for evaluating big architectural bets at {company}.",
            "How would you lead {company}'s transition to new technology stacks?",
            "Design an approach to standardizing systems across {company}'s teams.",
            "How do you balance innovation with maintaining {company}'s stability?",
            "Explain your strategy for improving {company}'s technical culture.",
            "How would you lead complex technical initiatives across {company}?",
            "Design a roadmap for improving {company}'s infrastructure efficiency.",
            "How would you establish technical excellence as {company}'s standard?",
            "Explain your approach to building reusable platforms at {company}.",
            "How do you drive adoption of new technical practices at {company}?",
            "Design a framework for technical decision-making at {company}.",
            "How would you address {company}'s most complex technical challenges?",
            "Explain your vision for {company}'s technical infrastructure.",
        ],
        "advanced": [
            "How would you architect {company}'s next-generation platform ecosystem?",
            "Design a 10-year technical strategy for {company}'s core systems.",
            "Explain how you would fundamentally improve {company}'s engineering productivity.",
            "Design an approach to making {company} the industry leader in system design.",
            "How would you lead {company}'s transition to quantum computing readiness?",
            "Explain your framework for navigating {company}'s biggest technical bets.",
            "Design a vision for {company}'s completely reimagined architecture.",
            "How would you build technical excellence across all of {company}?",
            "Explain your strategy for {company} to lead in distributed systems innovation.",
            "Design an approach to {company}'s technical autonomy vs standardization trade-off.",
            "How would you architect {company}'s systems for the next 50 years?",
            "Explain your vision for making {company}'s infrastructure self-evolving.",
            "Design a framework for {company}'s bold architectural transformations.",
            "How would you lead {company}'s transformation into a technology leader?",
            "Explain your approach to building {company}'s next platform revolution.",
            "Design a strategy for {company} to achieve technical parity with competitors.",
            "How would you architect systems that anticipate {company}'s future needs?",
            "Explain your vision for {company}'s engineering at an order of magnitude larger scale.",
            "Design an approach to making {company} the gold standard for system design.",
            "How would you build systems that adapt to unknown future requirements?",
        ],
    },
    "engineering_manager": {
        "beginner": [
            "What are the key responsibilities of an Engineering Manager at {company}?",
            "How do you approach building and scaling teams at {company}?",
            "Explain your philosophy on mentoring and developing engineers at {company}.",
            "What makes a good engineering culture at {company}?",
            "How do you approach performance management at {company}?",
            "Describe your experience with hiring at {company}.",
            "How do you balance business goals with engineering needs at {company}?",
            "Explain your approach to team communication at {company}.",
            "What is your leadership philosophy at {company}?",
            "How do you handle conflicts within your team at {company}?",
            "Describe your approach to career development for engineers at {company}.",
            "How do you measure team productivity at {company}?",
            "What makes a strong engineering team at {company}?",
            "How do you approach technical decision-making with your team at {company}?",
            "Explain your approach to handling underperformance at {company}.",
            "How do you foster innovation within your team at {company}?",
            "Describe your experience managing distributed teams at {company}.",
            "How do you approach quarterly planning with your team at {company}?",
            "What is your approach to retention at {company}?",
            "How do you build psychological safety in your team at {company}?",
        ],
        "intermediate": [
            "How would you scale a team from 5 to 50 engineers at {company}?",
            "Design an organization structure for a major {company} initiative.",
            "How would you improve engineering productivity across {company}?",
            "Explain your approach to building high-performing engineering organizations.",
            "How would you handle a major team restructuring at {company}?",
            "Design a hiring strategy for a critical {company} team.",
            "How would you develop future leaders from within at {company}?",
            "Explain your strategy for improving {company}'s code quality and practices.",
            "How would you navigate a major technical debt situation with your team?",
            "Design a career framework for your {company} organization.",
            "How would you improve cross-team collaboration at {company}?",
            "Explain your approach to managing upwards and influencing at {company}.",
            "How would you build accountability and ownership at {company}?",
            "Design an approach to handling rapid growth at {company}.",
            "How would you improve your team's impact on {company} business metrics?",
            "Explain your strategy for retaining top talent at {company}.",
            "How would you lead your team through a major crisis at {company}?",
            "Design a system for career growth and promotions at {company}.",
            "How would you improve diversity and inclusion in your team?",
            "Explain your approach to building resilient team culture.",
        ],
        "advanced": [
            "Design an engineering organization for {company} at 10x scale.",
            "How would you lead {company}'s engineering through major transformation?",
            "Explain your vision for {company}'s engineering culture and impact.",
            "Design a talent development strategy for {company}'s engineering org.",
            "How would you build world-class engineering leadership at {company}?",
            "Explain your approach to balancing growth with stability at {company}.",
            "Design a strategy for making {company} an employer of choice.",
            "How would you lead {company}'s engineering through unprecedented challenges?",
            "Explain your framework for making hard organizational decisions.",
            "Design an approach to building innovation into {company}'s culture.",
            "How would you create industry-leading engineering at {company}?",
            "Explain your vision for {company}'s diverse and inclusive engineering org.",
            "Design a system for identifying and developing future executives.",
            "How would you build trust and credibility across {company} leadership?",
            "Explain your approach to navigating complex stakeholder dynamics.",
            "Design a strategy for {company}'s engineering competitiveness.",
            "How would you balance short-term delivery with long-term capabilities?",
            "Explain your framework for organizational resilience and adaptability.",
            "Design an approach to making engineering decisions at the exec level.",
            "How would you build a legacy of impact at {company}?",
        ],
    },
    "product_manager": {
        "beginner": [
            "What does a Product Manager do at {company}?",
            "How do you approach understanding user needs at {company}?",
            "Explain your philosophy on prioritization at {company}.",
            "What makes a good product strategy at {company}?",
            "How do you work with engineering teams at {company}?",
            "Describe your approach to market research at {company}.",
            "How do you measure product success at {company}?",
            "Explain your approach to user feedback at {company}.",
            "What is your philosophy on product roadmaps at {company}?",
            "How do you approach competitive analysis at {company}?",
            "Describe your experience with {company} users and their pain points.",
            "How do you approach A/B testing at {company}?",
            "Explain your approach to product launch at {company}.",
            "What makes a compelling product vision at {company}?",
            "How do you balance user needs with business goals at {company}?",
            "Describe your experience with analytics at {company}.",
            "How do you approach technical feasibility discussions at {company}?",
            "Explain your approach to cross-functional collaboration.",
            "What metrics matter most for {company} products?",
            "How do you stay close to users at {company}?",
        ],
        "intermediate": [
            "How would you grow a {company} product from 1M to 100M users?",
            "Design a product strategy for a new {company} market.",
            "How would you pivot a {company} product based on market feedback?",
            "Explain your approach to building products for different {company} markets.",
            "How would you improve a struggling {company} product?",
            "Design a roadmap for a major {company} initiative.",
            "How would you build a product that drives {company} revenue?",
            "Explain your strategy for user acquisition at {company}.",
            "How would you handle declining engagement in a {company} product?",
            "Design a go-to-market strategy for a {company} product.",
            "How would you build a sustainable competitive advantage at {company}?",
            "Explain your approach to internationalization for {company} products.",
            "How would you navigate a major product crisis at {company}?",
            "Design a strategy for improving product engagement metrics.",
            "How would you balance short-term metrics with long-term user value?",
            "Explain your approach to building brand loyalty at {company}.",
            "How would you identify and enter new market opportunities?",
            "Design an approach to managing multiple product lines at {company}.",
            "How would you improve monetization while maintaining user trust?",
            "Explain your strategy for product-market fit optimization.",
        ],
        "advanced": [
            "Design the next billion-user product at {company}.",
            "How would you transform {company}'s product portfolio?",
            "Explain your vision for {company}'s product leadership position.",
            "Design a strategy for {company} to dominate multiple markets.",
            "How would you lead {company} through major product disruption?",
            "Explain your approach to anticipating market shifts at {company}.",
            "Design a system for continuous product innovation at {company}.",
            "How would you build {company}'s product into a platform?",
            "Explain your vision for {company}'s user experience in the future.",
            "Design an approach to {company} competing against new challengers.",
            "How would you make {company} the most loved brand in its category?",
            "Explain your strategy for {company} to expand into adjacent markets.",
            "Design a long-term product vision for {company}'s ecosystem.",
            "How would you navigate {company}'s path to market leadership?",
            "Explain your framework for making billion-dollar product bets.",
            "Design an approach to balancing innovation with execution at {company}.",
            "How would you build products that transcend current categories?",
            "Explain your vision for {company}'s product impact on society.",
            "Design a strategy for sustainable competitive advantage.",
            "How would you build an enduring {company} product legacy?",
        ],
    },
}

def generate_questions_for_company_role(company: str, role: str) -> dict:
    """Generate 60 questions (20 beginner, 20 intermediate, 20 advanced) for a company-role combo."""
    
    questions = []
    question_id = 1
    
    templates = QUESTION_TEMPLATES.get(role, {})
    
    for difficulty in ["beginner", "intermediate", "advanced"]:
        difficulty_templates = templates.get(difficulty, [])
        
        # If we don't have enough templates, repeat and cycle
        for i in range(20):
            template_idx = i % len(difficulty_templates) if difficulty_templates else 0
            template = difficulty_templates[template_idx] if difficulty_templates else f"{difficulty.capitalize()} Question {i+1}"
            
            question_text = template.format(company=company.capitalize())
            
            questions.append({
                "id": f"q_{question_id:03d}",
                "text": question_text,
                "difficulty": difficulty,
                "topic": f"{role.replace('_', ' ').title()} - {difficulty.capitalize()}",
                "company": company,
                "role": role
            })
            question_id += 1
    
    return {
        "company": company,
        "role": role,
        "questions": questions
    }


def main():
    """Generate all 25 company-role question files."""
    questions_dir = Path("data/questions")
    questions_dir.mkdir(parents=True, exist_ok=True)
    
    total = len(COMPANIES) * len(ROLES)
    count = 0
    
    for company in COMPANIES:
        for role in ROLES:
            count += 1
            context_name = f"{company}_{role}"
            
            try:
                result = generate_questions_for_company_role(company, role)
                
                # Save to file
                out_path = questions_dir / f"{context_name}_questions.json"
                out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                
                num_questions = len(result.get("questions", []))
                print(f"[{count}/{total}] ✓ {context_name}: {num_questions} questions")
            except Exception as e:
                print(f"[{count}/{total}] ✗ {context_name}: {str(e)}")
    
    print(f"\n[COMPLETE] Generated {total} question files with 60 questions each!")


if __name__ == "__main__":
    main()
