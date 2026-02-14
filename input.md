start writing a plan for the postgres container, see plan.md. 

│  │  tables:                                                                      │  │
│  │    users / roles     — reviewer accounts and RBAC                             │  │
│  │    cases             — case management records                                │  │
│  │    review_decisions  — alert dispositions and escalations                     │  │
│  │    policies          — lexicons, rules, thresholds    

functionally we need to:

have user groups and roles. An admin needs to be able to create users and assign them groups. The admin should also be 
able to update groups. 

further more we need to be able to create policies and assign them to users.

A policy consist of a set of rules, lets start with rules that are writen in KQL (kibana query language). 
A policcies are grouped in risk models.

Alerts are genered on events (documents in elasticsearch). The alert name and elestic event id should be stored in postgres

REview desictions are also stored in postgres.

A review decision consist of a review status and a comment. The review statussees are configurable. 

There should also be an audit trail for each review action. 

Also plan how to divede the tables into different schemas. 

Write the plan in a markdown file. 