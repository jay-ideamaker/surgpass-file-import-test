# backend/importer/views.py

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from bs4 import BeautifulSoup
import mammoth
from mammoth import images # <-- Important import
import io
import uuid
from supabase import create_client, Client
import traceback
import re

from .models import Question, Tag, AnswerChoice, Article, QuickHit, QuickHitAnswerChoice
from .enhanced_parser import parse_new_format_enhanced

def parse_and_save_docx(docx_file):
    """
    Parse the .docx file and save questions to the DB.
    Only handles new format with Blueprint tag structure.
    """
    print("\n[PARSER_START] Starting DOCX processing...")
    
    supabase: Client = create_client("https://vektbbzdrnqddjkcsyoc.supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZla3RiYnpkcm5xZGRqa2NzeW9jIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTc3NTk5NywiZXhwIjoyMDY1MzUxOTk3fQ.Q09i4OAI-xkTcoV-kwBeLgvy90D6M2OdaYg6v_rGmjE")

    def convert_image(image):
        with image.open() as image_stream:
            file_ext = image.content_type.split('/')[-1]
            file_name = f"{uuid.uuid4()}.{file_ext}"
            print(f"  [IMAGE_UPLOAD] Uploading image: {file_name}")
            supabase.storage.from_("question-images").upload(
                file_name, image_stream.read(), {"content-type": image.content_type}
            )
            public_url = supabase.storage.from_("question-images").get_public_url(file_name)
            print(f"  [IMAGE_UPLOAD] Success. URL: {public_url}")
            return {"src": public_url}

    docx_file.seek(0)
    html_result = mammoth.convert_to_html(docx_file, convert_image=images.img_element(convert_image))
    full_html = html_result.value

    # Parse using enhanced new format parser
    created_question_ids = parse_new_format_enhanced(full_html)
    
    print("\n[PARSER_END] Finished all processing.")
    return created_question_ids

def parse_old_format(full_html):
    """Parse the old format with [QUESTION_START] blocks"""
    question_html_blocks = full_html.split("<p>[QUESTION_START]</p>")[1:]
    print(f"[PARSER_INFO] Found {len(question_html_blocks)} question blocks to process (OLD FORMAT).")
    
    created_question_ids = []
    for i, block_html in enumerate(question_html_blocks):
        print(f"\n--- Parsing Question Block #{i + 1} (OLD FORMAT) ---")
        soup = BeautifulSoup(block_html, 'html.parser')

        # Parse old format metadata
        blueprint = _get_tag_content(soup, "[BLUEPRINT]:")
        subject = _get_tag_content(soup, "[SUBJECT]:")
        category = _get_tag_content(soup, "[CATEGORY]:")
        subcategory = _get_tag_content(soup, "[SUBCATEGORY]:")
        topic = _get_tag_content(soup, "[TOPIC]:")
        difficulty = _get_tag_content(soup, "[DIFFICULTY]:", as_float=True)
        question_text = _get_multiline_content(soup, "[QUESTION_TEXT_START]", "[QUESTION_TEXT_END]")
        short_explanation = _get_multiline_content(soup, "[SHORT_EXPLANATION_START]", "[SHORT_EXPLANATION_END]")
        full_explanation = _get_multiline_content(soup, "[FULL_EXPLANATION_START]", "[FULL_EXPLANATION_END]")
        
        # Create question with old format (no question_bank)
        question = Question.objects.create(
            blueprint=blueprint, subject=subject, category=category, subcategory=subcategory,
            topic=topic, difficulty=difficulty, question_text=question_text,
            short_explanation=short_explanation, full_explanation=full_explanation
        )
        
        # Handle tags, answers, articles, quickhits (same as before)
        _process_tags(soup, question)
        _process_answer_choices(soup, question)
        _process_articles(soup, question)
        _process_quickhits(soup, question)
        
        created_question_ids.append(question.id)
        print(f"--- Finished Processing Question Block #{i + 1} (OLD FORMAT) ---")
        
    return created_question_ids

def parse_new_format(full_html, supabase):
    """Parse the new format with 'Blueprint tag (ABSITE):' style tags"""
    return parse_new_format_enhanced(full_html)

def _parse_new_format_question(content):
    """Parse metadata from new format question content"""
    lines = content.split('\n')
    
    question_data = {}
    
    for line in lines[:20]:  # Check first 20 lines for metadata
        line = line.strip()
        
        if line.startswith('Blueprint tag ('):
            # Extract question bank and blueprint
            match = re.match(r'Blueprint tag \((ABSITE|ABS QE)\):\s*(.*)', line)
            if match:
                question_data['question_bank'] = match.group(1)
                question_data['blueprint'] = match.group(2).strip()
                
        elif line.startswith('Subject tag:'):
            question_data['subject'] = line.replace('Subject tag:', '').strip()
            
        elif line.startswith('Topic tag:'):
            question_data['topic'] = line.replace('Topic tag:', '').strip()
            
        elif line.startswith('Category tag:'):
            question_data['category'] = line.replace('Category tag:', '').strip()
            
        elif line.startswith('Subcategory tag:'):
            question_data['subcategory'] = line.replace('Subcategory tag:', '').strip()
    
    print(f"  [METADATA] Question Bank: {question_data.get('question_bank')}")
    print(f"  [METADATA] Blueprint: {question_data.get('blueprint')}")
    print(f"  [METADATA] Subject: {question_data.get('subject')}")
    print(f"  [METADATA] Topic: {question_data.get('topic')}")
    
    return question_data

def _extract_question_html(full_html, current_match, next_match):
    """Extract HTML portion for a specific question"""
    # This is a simplified approach - in practice you might need more sophisticated parsing
    # For now, let's just return the full HTML and let other functions handle it
    return full_html

def _process_new_format_content(soup, question, supabase):
    """Process content for new format questions"""
    # Extract question text, explanations, etc.
    # This will need to be adapted based on the exact structure of your new format
    
    # For now, let's try to find common patterns
    question_text = _extract_question_text_new_format(soup)
    if question_text:
        question.question_text = question_text
        question.save()
    
    # Extract key point and expanded explanation
    key_point = _extract_key_point_new_format(soup)
    if key_point:
        question.short_explanation = key_point
        question.save()
    
    expanded_explanation = _extract_expanded_explanation_new_format(soup)
    if expanded_explanation:
        question.full_explanation = expanded_explanation
        question.save()
    
    # Process answer choices, references, quickhits
    _process_new_format_answers(soup, question)
    _process_new_format_references(soup, question)
    _process_new_format_quickhits(soup, question)

def _extract_question_text_new_format(soup):
    """Extract the main question text from new format"""
    # Look for patterns that indicate question text
    # This will depend on your document structure
    return None

def _extract_key_point_new_format(soup):
    """Extract key point from new format"""
    # Look for "Key Point" section
    for p in soup.find_all('p'):
        text = p.get_text()
        if 'Key Point' in text:
            return text.replace('Key Point', '').strip()
    return None

def _extract_expanded_explanation_new_format(soup):
    """Extract expanded explanation from new format"""
    # Look for "Expanded Explanation" section
    for p in soup.find_all('p'):
        text = p.get_text()
        if 'Expanded Explanation' in text:
            return text.replace('Expanded Explanation', '').strip()
    return None

def _process_new_format_answers(soup, question):
    """Process answer choices for new format"""
    # This will need to be implemented based on your document structure
    pass

def _process_new_format_references(soup, question):
    """Process references for new format"""
    # Look for References section
    pass

def _process_new_format_quickhits(soup, question):
    """Process QuickHits for new format"""
    # Look for QUICKHITS section
    pass

# --- Helper functions for parsing (keeping existing ones and adding new) ---
def _get_tag_content(soup, tag, as_float=False):
    found_tag = soup.find('p', string=lambda t: t and t.startswith(tag))
    if not found_tag: return None
    content = found_tag.get_text(strip=True).replace(tag, '').strip()
    if as_float:
        try: return float(content)
        except (ValueError, TypeError): return None
    return content

def _get_multiline_content(soup, start_tag_text, end_tag_text):
    start_tag = soup.find(string=lambda t: t and start_tag_text in t)
    if not start_tag: return ""
    content_html = []
    start_p = start_tag.find_parent('p')
    if not start_p: return ""
    for sibling in start_p.find_next_siblings():
        if end_tag_text in sibling.get_text(): break
        content_html.append(str(sibling))
    return "".join(content_html)

def _process_tags(soup, question):
    """Process tags for a question"""
    tags_str = _get_tag_content(soup, "[TAGS]:")
    print(f"  [TAGS] Found raw tags string: '{tags_str}'")
    if tags_str:
        tag_names = [name.strip() for name in tags_str.split(',') if name.strip()]
        for name in tag_names:
            tag, created = Tag.objects.get_or_create(name=name)
            question.tags.add(tag)
            print(f"    [DB_SAVE] Associated Tag: '{name}' (Created new: {created})")

def _process_answer_choices(soup, question):
    """Process answer choices for a question"""
    answers_html = _get_multiline_content(soup, "[ANSWERS_START]", "[ANSWERS_END]")
    if answers_html:
        answer_soup = BeautifulSoup(answers_html, 'html.parser')
        answer_tags = answer_soup.find_all('p', string=lambda t: t and t.startswith('[ANSWER]:'))
        print(f"  [ANSWERS] Found {len(answer_tags)} answer choices.")
        for ans_tag in answer_tags:
            text = ans_tag.get_text(strip=True).replace('[ANSWER]:', '').strip()
            is_correct = '[x]' in text
            text = text.replace('[ ]', '').replace('[x]', '').strip()
            
            explanation_tag = ans_tag.find_next_sibling('p', string=lambda t: t and t.startswith('[EXPLANATION]:'))
            explanation_text = explanation_tag.get_text(strip=True).replace('[EXPLANATION]:', '').strip() if explanation_tag else ""

            if text:
                print(f"    [PARSED_ANSWER] Text: '{text}', Correct: {is_correct}, Explanation: '{explanation_text}'")
                AnswerChoice.objects.create(question=question, text=text, is_correct=is_correct, explanation=explanation_text)

def _process_articles(soup, question):
    """Process articles for a question"""
    articles_html = _get_multiline_content(soup, "--- Citations / Articles", "--- QuickHits ---")
    if articles_html:
        article_soup = BeautifulSoup(articles_html, 'html.parser')
        article_tags = article_soup.find_all('p', string=lambda t: t and t.startswith('[ARTICLE]:'))
        print(f"  [ARTICLES] Found {len(article_tags)} article lines.")
        for p_tag in article_tags:
            text = p_tag.get_text(strip=True).replace('[ARTICLE]:', '').strip()
            if text:
                print(f"    [PARSED_ARTICLE] Text: '{text}'")
                Article.objects.create(question=question, text=text)

def _process_quickhits(soup, question):
    """Process QuickHits for a question"""
    quickhits_html = _get_multiline_content(soup, "--- QuickHits ---", "[QUESTION_END]")
    if quickhits_html:
        qh_blocks = quickhits_html.split('[QUICKHIT_START]')[1:]
        print(f"  [QUICKHITS] Found {len(qh_blocks)} QuickHit blocks.")
        for qh_block_html in qh_blocks:
            qh_soup = BeautifulSoup(qh_block_html, 'html.parser')
            qh_question_text = _get_tag_content(qh_soup, '[QUESTION]:')
            qh_rationale_text = _get_tag_content(qh_soup, '[RATIONALE]:')

            if qh_question_text:
                print(f"    [PARSED_QH] Question: '{qh_question_text}'")
                quick_hit = QuickHit.objects.create(parent_question=question, question_text=qh_question_text, rationale=qh_rationale_text)
                for ans_tag in qh_soup.find_all('p', string=lambda t: t and t.startswith('[ANSWER]:')):
                    text = ans_tag.get_text(strip=True).replace('[ANSWER]:', '').strip()
                    is_correct = '[x]' in text
                    text = text.replace('[ ]', '').replace('[x]', '').strip()
                    if text:
                        print(f"      [PARSED_QH_ANSWER] Text: '{text}', Correct: {is_correct}")
                        QuickHitAnswerChoice.objects.create(quick_hit=quick_hit, text=text, is_correct=is_correct)

# --- API View ---
class DocxUploadView(APIView):
    def post(self, request, *args, **kwargs):
        docx_file = request.FILES.get('file')
        if not docx_file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            file_obj = io.BytesIO(docx_file.read())
            question_ids = parse_and_save_docx(file_obj)
            
            message = f"Successfully processed and created {len(question_ids)} questions!"
            
            return Response(
                {"message": message, "question_ids": question_ids}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            traceback.print_exc()
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)