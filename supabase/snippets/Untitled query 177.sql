INSERT INTO public.profiles (id, email, display_name, role, verification_status)
SELECT id, email, 'Admin', 'admin', 'verified'
FROM auth.users
WHERE email = 'admin@feelseka.com'
ON CONFLICT (id) DO UPDATE
  SET role = 'admin', verification_status = 'verified';