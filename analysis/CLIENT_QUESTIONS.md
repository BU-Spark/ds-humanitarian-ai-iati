# Client questions for the summer-prototype review

Prepared October 7, 2026, from the code, supplied graph exports, project brief, and September 25 kickoff notes. Findings and evidence are in [SUMMER_PROTOTYPE_REVIEW.md](SUMMER_PROTOTYPE_REVIEW.md).

Suggested opening: “We reproduced the core filtering behavior and reviewed the exported graph. The foundation is useful, but we need shared definitions for history, funding, and data quality before automating it. These decisions will determine what the graph can answer reliably.”

## First meeting: decisions that unblock implementation

1. **What is the minimum successful December handoff?** At kickoff you emphasized a durable foundation and flexible deliverables. Would you prioritize a validated daily pipeline with historical snapshots and Neo4j before a broader Graph RAG demo? Which deliverables may remain exploratory? This resolves the difference between the full written deliverable list and the flexibility in the kickoff discussion.

2. **What should “historical data” let a user ask?** Do you want transactions grouped by their economic date, the exact data that was available on a past date, or comparisons between revisions? How long should we retain snapshots, and is there an existing archive to backfill? The prototype currently overwrites files, so saving transaction dates alone will not meet the snapshot-history need. (F2, F7)

3. **When we say “funding,” which measure should be the default?** Money received, commitments, disbursements, expenditure, or budgets? Should these always be shown separately? How should reversals, negative adjustments, and the same transfer reported by multiple organizations be handled? Current funder totals mix transaction types, and 5,337 values are negative. (F5, F10)

4. **Are these three publishers and this hotspot list still the intended scope?** Should we keep the June–November 2026 list fixed for a reproducible comparison or track changes to hotspot membership over time? Should analysis include all historic activities, only active activities, or a selected period? Is subnational matching required this semester? (F6, F11)

5. **What should qualify as hunger-related work?** Should general emergency relief, cash transfers, livelihoods, and agriculture all count? Can a domain reviewer label a small sample of included and excluded records? About 85% of the current activities enter through keywords, and the emergency-code toggle is ineffective. (F4, F11)

6. **Can you help validate Oxfam America's coverage?** We have only 11 retained activities, with starts in 2017–2018 and record updates in July 2020. Is that expected, a historical dataset, or evidence that we need a different source or publisher identifier? Should comparisons explicitly flag unequal periods and missing coverage? These observations do not establish that Oxfam America has stopped publishing. (Snapshot profile)

7. **Can you share the exact WFP reference-field anomaly from the summer review?** We need the source XML, activity identifier, dataset/version, exact field, and expected interpretation. Should a country code in an activity-reference field be quarantined, retained as an unresolved value, or mapped using an approved rule? The current parser drops activity-reference attributes, so the exported CSV cannot settle this. (F7)

8. **What should happen when one publisher's daily data fails validation?** Keep the entire previous snapshot, update successful publishers with visible freshness labels, or block publication? Who should review alerts, and what delay is acceptable? Today failures can appear successful and missing inputs can empty the graph. (F1)

## Follow-up decisions for schema, analytics, and Graph RAG

9. **Which duplicate version should win?** Latest publisher update, preferred dataset, or manual review when records conflict? Must we retain all conflicting originals? The parser currently keeps the first file occurrence even if a newer or eligible record appears later. (F3)

10. **Who can approve organization merges and aliases?** Should equally named organizations stay separate pending review? How should we represent national branches and historical renames? Can we obtain a reference mapping, including Oxfam America's differing identifier formats? (F8)

11. **How should funding be allocated across countries and sectors?** Should transaction-level coding take priority, followed by activity percentages? If percentages are absent, should we report the amount as unallocated? Is proportional allocation an acceptable estimate, clearly labeled? Current analytics attach all activity transactions to every selected hotspot on that activity. (F6)

12. **What must a funding-flow diagram demonstrate?** An illustrative relationship overview or an auditable delivery chain? WFP has expenditure but no disbursement rows in the supplied slice, so the current outgoing Sankey misses that spending. Should missing counterparties, exclusions, negative adjustments, and top-N omissions be displayed? (F5)

13. **How should revised and indicative budgets appear?** Should the latest applicable revision replace an original for the same period, and should indicative budgets be displayed separately? Most budget rows here are indicative, which makes a committed-only view a narrow comparison. (F10)

14. **Which five questions must Graph RAG answer correctly, and who will validate the answers?** For example: “What incoming funds did publisher X report for country Y in period Z, in USD, as of snapshot D?” Agree the expected records/calculation, required citations, acceptable latency, and what an “insufficient data” response should say.

15. **Does identifying places needing more aid require an external needs dataset?** The current graph represents published activities and financial records. It does not contain a validated measure of unmet need. Which needs indicators and authoritative sources would support the question raised at kickoff, and is that integration within fall scope?

16. **Which source evidence should users be able to open from an answer or graph node?** Original XML, an archived record, a publisher page, or an IATI record viewer? Does the claimed summer click-through refer to another demo/version? Should “locations” mean countries or subnational places? (F7 and brief/implementation differences)

17. **Which optional entities matter for the first Neo4j schema?** Results/indicators are not currently extracted, and emergency/region/policy-marker/related-activity exports are empty. Should these be investigated now, or should the first release concentrate on organizations, activities, transactions, geography, and provenance?

18. **What environment and operating budget are actually available for the handoff?** Confirm the owner of Neo4j, scheduled jobs, raw snapshot storage, model access, and monitoring. Who maintains these after December? Is testing Z.AI and comparing multiple models required or exploratory, and which providers/languages are approved?

19. **What evidence is sufficient for the raw-versus-cleaned demonstration?** Would one fully traceable three-publisher example plus a bounded broader-corpus sample satisfy the goal? What storage/compute limit should stop the broader experiment? The brief does not require cleaning the complete IATI corpus.

20. **Can maintainers confirm the missing handoff materials and intended license?** Request original raw snapshots, download manifest, anomaly examples, cleaning decisions, validated outputs, and any existing Neo4j/Cypher work. Space metadata says MIT while the repository license is GPLv3. Confirm which applies before documenting redistribution terms.

## Decisions to record after the meeting

Record the agreed minimum deliverables; history semantics and retention; funding measures; scope and date window; validation/failure policy; identity-resolution reviewer; five acceptance questions; infrastructure owner/budget; and deferred work. Assign an owner and target date to each unresolved question.

The engineering team can fix the toggle, sync documentation, stale bundle behavior, fixture coverage, and duplicate-edge handling without asking the client to debug code. Client time is most useful for domain meaning, priorities, and acceptance criteria.
