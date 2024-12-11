<div align="center">
  <img src="/assets/BS_logo.png" alt="BuildSync Logo" width="200px">
  <h1>BuildSync</h1>
</div>

Natural Language-Driven Building Information Modeling (BIM) Generation

## Overview

BuildSync transforms natural language descriptions into detailed architectural models, bridging the gap between human communication and technical BIM implementation. By leveraging advanced language models and a modular architecture, BuildSync enables intuitive creation of Industry Foundation Classes (IFC) models through simple text descriptions.

## 🌟 Key Features

- **Natural Language Processing**: Convert plain English descriptions into architectural designs
- **Real-time IFC Generation**: Instantly create and modify IFC models
- **Comprehensive Component Support**: 
  - Walls, beams, and columns
  - Multi-story buildings
  - Material specifications
- **Smart Search & Modification**: Easily find and update building elements
- **Flexible Model Management**: Session-based model storage and manipulation

## 🏗️ Architecture

### Core Components

1. **Language Processing Engine**
   - Powered by Claude 3.5 Sonnet
   - Converts natural language into structured commands
   - Intelligent context understanding

2. **Tool System**
   - Specialized functions for building element creation
   - Coordinate system management
   - Material and dimension handling

3. **IFC Model Manager**
   - Real-time IFC file generation
   - Session-based model persistence
   - Efficient model updates and modifications

## 🚀 Getting Started

### Prerequisites

```bash
# Required dependencies
python 3.8+
ifcopenshell
numpy
socket.io
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/aliyanishfaq/bsn-server.git
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
# Create .env file
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
```

### Quick Start

```python
# Initialize a new session
session_id = "example_session"
create_session(session_id)

# Create a building story
create_building_story(session_id, elevation=0.0, name="Ground Floor")

# Add a wall
create_wall(
    session_id,
    story_n=1,
    start_coord="0,0,0",
    end_coord="10,0,0",
    height=10
)
```

## 💻 Usage Examples

### Creating a Basic Room

```python
# Create four walls to form a room
create_wall(sid, "0,0,0", "10,0,0", height=10)  # Front wall
create_wall(sid, "10,0,0", "10,10,0", height=10)  # Right wall
create_wall(sid, "10,10,0", "0,10,0", height=10)  # Back wall
create_wall(sid, "0,10,0", "0,0,0", height=10)  # Left wall
```

### Adding Structural Elements

```python
# Add a beam
create_beam(
    sid,
    start_coord="0,0,10",
    end_coord="10,0,10",
    section_name="W16X40",
    story_n=1
)

# Add a column
create_column(
    sid,
    location="5,5,0",
    height=10,
    story_n=1
)
```

## 🔍 Model Management

### Searching Elements

```python
# Find all walls in the model
search_canvas(sid, "find all walls")

# Find specific elements
search_canvas(sid, "find leftmost wall")
```

### Modifying Elements

```python
# Delete specific elements
delete_element(sid, element_id)
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/new_feature`)
3. Commit your changes (`git commit -m 'Add some new_feature'`)
4. Push to the branch (`git push origin feature/new_feature`)
5. Open a Pull Request


---

<div align="center">
BuildSync Team
</div>
