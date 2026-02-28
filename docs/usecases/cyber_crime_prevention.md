# Cyber Crime Prevention

Beyond regulatory compliance, Umbrella serves as a powerful defense layer against modern cyber threats. By ingesting communications from all corporate channels—not just email—and applying real-time AI analysis, Umbrella helps organizations detect and prevent sophisticated cyber crimes before they result in data breaches or financial loss.

## Phishing and Social Engineering

Traditional email gateways often struggle with sophisticated phishing attacks, especially those that originate from compromised internal accounts or move quickly to "off-channel" platforms like Teams or Slack.

*   **Cross-Channel Detection**: Umbrella monitors multiple communication streams simultaneously. A phishing link sent via email that is followed by a "nudge" on Microsoft Teams is correlated by Umbrella's **Entity Resolution** engine, flagging the coordinated nature of the attack.
*   **NLP-Based Intent Analysis**: Instead of relying solely on blacklisted URLs, Umbrella’s **NLP Enrichment** service analyzes the *intent* of the message. It can detect high-pressure tactics, unusual requests for sensitive information, or slight deviations in a colleague's writing style that suggest account takeover.

## Business Email Compromise (BEC)

BEC remains one of the most financially damaging forms of cyber crime. It typically involves an attacker impersonating a high-level executive or a trusted vendor to authorize fraudulent wire transfers.

*   **Outlier & Anomaly Detection**: Umbrella’s AI layer identifies statistical deviations in communication patterns. If a CFO suddenly messages a junior accountant in the middle of the night via a new channel to request an urgent payment, Umbrella’s **Anomaly Detector** flags this as a high-risk event based on historical communication frequency and timing.
*   **Tone and Sentiment Shift**: BEC attacks often involve a shift in authority and urgency. Umbrella monitors the sentiment and tone of conversations, alerting security teams when the behavioral profile of an interaction deviates from the norm.

## Insider Threats and Data Leakage

Preventing the unauthorized export of sensitive data (PII, IP, or trade secrets) is a critical component of cyber security.

*   **Lexicon & Pattern Matching**: Umbrella's NLP service uses advanced lexicons to identify sensitive data patterns (e.g., project codenames, credit card numbers, or proprietary formulas) across all indexed communications.
*   **Behavioral Risk Profiling**: By aggregating activity across all channels, Umbrella builds a **Behavioral Risk Profile** for every entity. Sudden spikes in "off-hours" activity or an increase in communications with external, unauthorized domains can trigger proactive alerts for human review.

## Incident Response & Forensics

When a security incident occurs, speed of investigation is paramount.

*   **Unified Search & Threading**: Umbrella’s **Email Threading** and **Semantic Search** allow investigators to reconstruct the entire lifecycle of an attack across all platforms in seconds, rather than hours spent searching siloed systems.
*   **Immutable Audit Trail**: Every communication ingested into Umbrella is archived in S3 and indexed in Elasticsearch, providing an immutable record that is essential for post-incident forensics and reporting to law enforcement or regulators.
