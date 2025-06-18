import { createClient } from '@supabase/supabase-js';

const supabaseUrl = "https://vektbbzdrnqddjkcsyoc.supabase.co";
const supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZla3RiYnpkcm5xZGRqa2NzeW9jIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3NzU5OTcsImV4cCI6MjA2NTM1MTk5N30.0HphSM6LkCFCPLqI1O5W0sFDSUltI9i81ECy9dhwLPY";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);