# importer/models.py
from django.db import models
import uuid

# A simple model for our tags to enable a many-to-many relationship.
class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True, primary_key=True)

    def __str__(self):
        return self.name

# The main model for a single parent question.
class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # --- Metadata Fields ---
    blueprint = models.CharField(max_length=255, blank=True, null=True)
    subject = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    subcategory = models.CharField(max_length=255, blank=True, null=True)
    topic = models.CharField(max_length=255, blank=True, null=True)
    difficulty = models.FloatField(blank=True, null=True)
    
    # Many-to-many relationship for tags
    tags = models.ManyToManyField(Tag, blank=True, related_name="questions")

    # --- Content Fields ---
    question_text = models.TextField(blank=True, null=True)
    short_explanation = models.TextField(blank=True, null=True)
    full_explanation = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question: {self.topic or 'Untitled'}"

# A model for each of the 5 multiple-choice answers for a parent question.
class AnswerChoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answer_choices")
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    explanation = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Answer for Q: {self.question.id} - {'Correct' if self.is_correct else 'Incorrect'}"

# A model for each article/citation linked to a question.
class Article(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="articles")
    text = models.TextField()

    def __str__(self):
        return self.text[:80]

# A model for each QuickHit associated with a parent question.
class QuickHit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="quick_hits")
    question_text = models.TextField()
    rationale = models.TextField()

    def __str__(self):
        return f"QuickHit for Q: {self.parent_question.id}"

# A model for each answer choice within a single QuickHit.
class QuickHitAnswerChoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quick_hit = models.ForeignKey(QuickHit, on_delete=models.CASCADE, related_name="answers")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"QH Answer: {self.text[:50]}"