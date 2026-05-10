import 'package:flutter/material.dart';

import '../services/api.dart';
import '../services/auth_store.dart';
import '../services/fcm_service.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _pw = TextEditingController();
  bool _busy = false;
  bool _registerMode = false;
  String? _err;

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _err = null;
    });
    try {
      final fn = _registerMode ? Api.register : Api.login;
      final tok = await fn(_email.text.trim(), _pw.text);
      Api.setToken(tok);
      await AuthStore.save(tok);
      await FcmService.registerWithBackend();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const HomeScreen()));
    } catch (e) {
      // Avoid exposing raw server errors to the UI
      setState(() => _err = 'Login failed. Check your email and password.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_registerMode ? 'Register' : 'Login')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(controller: _email, decoration: const InputDecoration(labelText: 'Email')),
            TextField(controller: _pw, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
            const SizedBox(height: 16),
            if (_err != null) Text(_err!, style: const TextStyle(color: Colors.red)),
            FilledButton(
              onPressed: _busy ? null : _submit,
              child: Text(_registerMode ? 'Create account' : 'Sign in'),
            ),
            TextButton(
              onPressed: () => setState(() => _registerMode = !_registerMode),
              child: Text(_registerMode ? 'Have an account? Sign in' : 'Need an account? Register'),
            ),
          ],
        ),
      ),
    );
  }
}
