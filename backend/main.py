from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import json
import os
from datetime import datetime
from pathlib import Path

# Initialize FastAPI
app = FastAPI()

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-api-key-here")
genai.configure(api_key=GEMINI_API_KEY)

# Database file path
DB_FILE = "reviews.json"

# Request/Response models
class ReviewSubmission(BaseModel):
    rating: int
    review_text: str

class ReviewResponse(BaseModel):
    ai_response: str
    success: bool

# Helper functions
def load_reviews():
    """Load reviews from JSON file"""
    if Path(DB_FILE).exists():
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return []

def save_reviews(reviews):
    """Save reviews to JSON file"""
    with open(DB_FILE, 'w') as f:
        json.dump(reviews, f, indent=2)

def generate_ai_response(rating: int, review_text: str) -> str:
    """Generate AI response for customer review"""
    prompt = f"""You are a helpful customer service AI. A customer left the following review:

Rating: {rating}/5
Review: {review_text}

Generate a professional, empathetic response acknowledging their feedback. 
Keep it concise (2-3 sentences). Match the tone:
- 5 stars: Thank them and ask them to share
- 1-2 stars: Apologize and offer solutions
- 3-4 stars: Thank them and suggest improvements

Response:"""
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"

def generate_ai_summary(review_text: str, rating: int) -> str:
    """Generate AI summary of the review"""
    prompt = f"""Summarize this customer review in ONE sentence. Focus on sentiment and topic:

Review: {review_text}
Rating: {rating}/5

Summary:"""
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Unable to generate summary"

def generate_recommended_action(review_text: str, rating: int, summary: str) -> str:
    """Generate recommended action for the review"""
    prompt = f"""Based on this customer review, suggest ONE action:

Review: {review_text}
Rating: {rating}/5
Summary: {summary}

Choose from:
- Reply and offer compensation
- Share positive feedback on social media
- Investigate issue further
- No action needed
- Follow up with customer

Recommended Action:"""
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Unable to generate action"

# API Routes

@app.get("/")
def read_root():
    return {"message": "Review Feedback System API is running"}

@app.post("/api/submit-review", response_model=ReviewResponse)
def submit_review(submission: ReviewSubmission):
    """Submit a review and get AI-generated response"""
    
    # Validate rating
    if not 1 <= submission.rating <= 5:
        return ReviewResponse(ai_response="Invalid rating", success=False)
    
    if not submission.review_text.strip():
        return ReviewResponse(ai_response="Review text cannot be empty", success=False)
    
    try:
        # Generate AI content
        ai_response = generate_ai_response(submission.rating, submission.review_text)
        ai_summary = generate_ai_summary(submission.review_text, submission.rating)
        ai_action = generate_recommended_action(submission.review_text, submission.rating, ai_summary)
        
        # Create review object
        review = {
            "id": str(datetime.now().timestamp()),
            "user_rating": submission.rating,
            "user_review": submission.review_text,
            "ai_response": ai_response,
            "ai_summary": ai_summary,
            "ai_recommended_action": ai_action,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Save to database
        reviews = load_reviews()
        reviews.append(review)
        save_reviews(reviews)
        
        return ReviewResponse(ai_response=ai_response, success=True)
    
    except Exception as e:
        return ReviewResponse(ai_response=f"Error: {str(e)}", success=False)

@app.get("/api/reviews")
def get_all_reviews():
    """Get all reviews (for admin dashboard)"""
    reviews = load_reviews()
    return {"reviews": reviews, "total": len(reviews)}

@app.get("/api/reviews/{review_id}")
def get_review(review_id: str):
    """Get specific review details"""
    reviews = load_reviews()
    for review in reviews:
        if review["id"] == review_id:
            return review
    return {"error": "Review not found"}

@app.post("/api/reviews/{review_id}/status")
def update_review_status(review_id: str, status: str):
    """Update review status (admin only)"""
    reviews = load_reviews()
    for review in reviews:
        if review["id"] == review_id:
            review["status"] = status
            save_reviews(reviews)
            return {"success": True, "message": "Status updated"}
    return {"success": False, "error": "Review not found"}

@app.get("/api/analytics")
def get_analytics():
    """Get dashboard analytics"""
    reviews = load_reviews()
    if not reviews:
        return {
            "total_reviews": 0,
            "average_rating": 0,
            "rating_distribution": {}
        }
    
    ratings = [r["user_rating"] for r in reviews]
    distribution = {i: ratings.count(i) for i in range(1, 6)}
    
    return {
        "total_reviews": len(reviews),
        "average_rating": sum(ratings) / len(ratings),
        "rating_distribution": distribution
    }

# Run with: uvicorn main:app --reload
