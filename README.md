🚦 TrafficVerse
Natural Language Traffic Simulation and Counterfactual Decision Engine for Bengaluru

TrafficVerse is a conversational traffic decision support system that allows users to ask what if traffic questions in natural language and explore the potential impact of road closures, diversions, and traffic interventions before implementing them on real roads.

Instead of reacting to congestion after a traffic intervention, TrafficVerse helps simulate its potential impact beforehand.

🌐 Live Demo
🚀 Try TrafficVerse

Live Application
https://trafficverse-971498899615.asia-south1.run.app/

💻 Source Code

GitHub Repository
https://github.com/aksha7746-tech/trafficverse

🎯 The Problem

Bengaluru's traffic network is highly interconnected.
A decision made at one junction or corridor can create unexpected congestion somewhere else. Closing a road, diverting vehicles, or modifying traffic flow may solve a local problem while simultaneously creating a larger downstream bottleneck.

Consider a scenario such as:
What happens if the Outer Ring Road near Bellandur is closed for 30 minutes during morning peak?

A traffic controller needs to understand several consequences.

Which corridor will be affected?
How much traffic may be displaced?
Which alternative corridors can absorb the displaced traffic?
How much could average speed decrease?
What is the overall congestion risk?
How should emergency vehicles be routed?

Traditional approaches often depend on historical information, manual analysis, or trial and error.
TrafficVerse explores a different approach.
Simulate first. Understand the consequences. Make a better decision.

💡 What is TrafficVerse?

TrafficVerse is a prototype counterfactual traffic simulation and decision support system built around Bengaluru traffic data.
Users can describe a traffic intervention in natural language.
Example:
Close Outer Ring Road near Bellandur for 30 minutes during morning peak.

TrafficVerse interprets the scenario and produces an estimated impact analysis covering:

Affected traffic corridor
Baseline traffic volume
Estimated redirected traffic
Estimated speed impact
Estimated congestion increase
Alternative corridors
Emergency routing recommendation
Overall risk level

The goal is to make traffic simulation accessible through a conversational interface rather than requiring users to manually configure a complex simulation model.


🔄 Counterfactual Simulation

TrafficVerse evaluates a hypothetical intervention without requiring it to actually happen on the road.

The conceptual process is:

Current Traffic Conditions
            ↓
"What if this road is closed?"
            ↓
Estimate Displaced Traffic
            ↓
Evaluate Surrounding Corridors
            ↓
Estimate Network Impact
            ↓
Recommend Alternatives

This enables what if decision making before real world deployment.

📊 Traffic Data Analysis

The application uses traffic volume and average speed data across Bengaluru corridors.

The current dataset includes:

Silk Board Junction
Hosur Road
Outer Ring Road
BTM Layout
Electronic City Road
HSR Layout
Madiwala
Bommanahalli

Traffic is represented across different time periods, vehicle types, traffic volumes, and average speeds.

Vehicle categories include:

🚗 Cars
🏍️ Bikes
🚌 Buses
🚚 Trucks
🛺 Autos
🛣️ Alternative Route Analysis

When a corridor is affected, TrafficVerse evaluates other available corridors and ranks them based on traffic conditions.

This helps answer:

If this corridor becomes unavailable, where should traffic be redirected?

🚑 Emergency Routing Support

TrafficVerse also provides an emergency routing recommendation.

The intention is to identify alternative corridors when the affected road should be avoided, particularly for scenarios where emergency response time matters.

⚠️ Risk Assessment

The simulation produces an estimated risk level based on the projected impact.

Current categories:

🟢 LOW

🟠 MEDIUM

🔴 HIGH

This provides a quick way for a traffic operator to understand whether a proposed intervention may have relatively limited or significant network consequences.

🧠 How It Works

<img width="1536" height="1024" alt="8bb136a4-ba04-46ab-988a-21ccafbef0d7" src="https://github.com/user-attachments/assets/473a8148-453d-46cd-9c70-88abd2b423eb" />


☁️ Google Cloud

TrafficVerse uses Google Cloud as the foundation for its data and deployment layer.

Current Cloud Components
Component	Purpose
Google BigQuery	Stores and queries traffic data
Google Cloud Run	Hosts the deployed application
Google Cloud Platform	Cloud infrastructure
Streamlit	Interactive application interface
Python	Simulation and application logic



