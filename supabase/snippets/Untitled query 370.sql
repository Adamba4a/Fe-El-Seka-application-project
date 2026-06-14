SELECT
  u.id,
  u.email,
  p.role,
  p.display_name
FROM auth.users u
LEFT JOIN public.profiles p ON p.id = u.id
ORDER BY u.created_at DESC;