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

from .models import Question, Tag, AnswerChoice, Article, QuickHit, QuickHitAnswerChoice

def parse_and_save_docx(docx_file):
    """
    Top-level function to parse the .docx file and save questions to the DB.
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

    question_html_blocks = full_html.split("<p>[QUESTION_START]</p>")[1:]
    print(f"[PARSER_INFO] Found {len(question_html_blocks)} question blocks to process.")
    
    created_question_ids = []
    for i, block_html in enumerate(question_html_blocks):
        print(f"\n--- Parsing Question Block #{i + 1} ---")
        soup = BeautifulSoup(block_html, 'html.parser')

        # --- 1. Extract and Log Metadata ---
        blueprint = _get_tag_content(soup, "[BLUEPRINT]:")
        subject = _get_tag_content(soup, "[SUBJECT]:")
        category = _get_tag_content(soup, "[CATEGORY]:")
        subcategory = _get_tag_content(soup, "[SUBCATEGORY]:")
        topic = _get_tag_content(soup, "[TOPIC]:")
        difficulty = _get_tag_content(soup, "[DIFFICULTY]:", as_float=True)
        question_text = _get_multiline_content(soup, "[QUESTION_TEXT_START]", "[QUESTION_TEXT_END]")
        short_explanation = _get_multiline_content(soup, "[SHORT_EXPLANATION_START]", "[SHORT_EXPLANATION_END]")
        full_explanation = _get_multiline_content(soup, "[FULL_EXPLANATION_START]", "[FULL_EXPLANATION_END]")
        
        print(f"  [METADATA] Blueprint: {blueprint}")
        print(f"  [METADATA] Subject: {subject}")
        print(f"  [METADATA] Category: {category}")
        print(f"  [METADATA] Subcategory: {subcategory}")
        print(f"  [METADATA] Topic: {topic}")
        print(f"  [METADATA] Difficulty: {difficulty}")
        print(f"  [CONTENT] Question Text found: {'Yes' if question_text else 'No'}")
        print(f"  [CONTENT] Short Explanation found: {'Yes' if short_explanation else 'No'}")
        print(f"  [CONTENT] Full Explanation found: {'Yes' if full_explanation else 'No'}")

        # Create the main Question object
        question = Question.objects.create(
            blueprint=blueprint, subject=subject, category=category, subcategory=subcategory,
            topic=topic, difficulty=difficulty, question_text=question_text,
            short_explanation=short_explanation, full_explanation=full_explanation
        )
        print(f"  [DB_SAVE] Created Question object with ID: {question.id}")

        # --- 2. Handle Tags ---
        tags_str = _get_tag_content(soup, "[TAGS]:")
        print(f"  [TAGS] Found raw tags string: '{tags_str}'")
        if tags_str:
            tag_names = [name.strip() for name in tags_str.split(',') if name.strip()]
            for name in tag_names:
                tag, created = Tag.objects.get_or_create(name=name)
                question.tags.add(tag)
                print(f"    [DB_SAVE] Associated Tag: '{name}' (Created new: {created})")

        # --- 3. Handle Answer Choices ---
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

        # --- 4. Handle Articles ---
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

        # --- 5. Handle QuickHits ---
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

        created_question_ids.append(question.id)
        print(f"--- Finished Processing Question Block #{i + 1} ---")
        
    print("\n[PARSER_END] Finished all processing.")
    return created_question_ids

# --- Helper functions for parsing ---
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
    # Find the parent <p> tag of the start text
    start_p = start_tag.find_parent('p')
    if not start_p: return ""
    for sibling in start_p.find_next_siblings():
        if end_tag_text in sibling.get_text(): break
        content_html.append(str(sibling))
    return "".join(content_html)

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