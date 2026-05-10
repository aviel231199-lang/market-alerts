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
  final _code = TextEditingController();
  bool _busy = false;
  bool _registerMode = false;
  String? _err;

  Future<void> _submit() async {
    setState(() { _busy = true; _err = null; });
    try {
      final String tok;
      if (_registerMode) {
        tok = await Api.register(_email.text.trim(), _pw.text, inviteCode: _code.text.trim());
      } else {
        tok = await Api.login(_email.text.trim(), _pw.text);
      }
      Api.setToken(tok);
      await AuthStore.save(tok);
      await FcmService.registerWithBackend();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const HomeScreen()));
    } catch (e) {
      setState(() => _err = _registerMode
          ? 'ההרשמה נכשלה. בדוק שהקוד תקין ולא שומש.'
          : 'כניסה נכשלה. בדוק אימייל וסיסמה.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('📈', style: TextStyle(fontSize: 52)),
                const SizedBox(height: 8),
                Text(
                  'Market Alerts',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 32),

                // Email
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'אימייל',
                    prefixIcon: Icon(Icons.email_outlined),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),

                // Password
                TextField(
                  controller: _pw,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'סיסמה',
                    prefixIcon: Icon(Icons.lock_outline),
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: _registerMode ? null : (_) => _submit(),
                ),

                // Invite code — only on register
                if (_registerMode) ...[
                  const SizedBox(height: 12),
                  TextField(
                    controller: _code,
                    decoration: const InputDecoration(
                      labelText: 'קוד גישה',
                      hintText: 'הכנס את הקוד שקיבלת',
                      prefixIcon: Icon(Icons.vpn_key_outlined),
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _submit(),
                  ),
                ],

                const SizedBox(height: 20),

                if (_err != null) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red.withOpacity(.3)),
                    ),
                    child: Text(_err!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                  ),
                  const SizedBox(height: 12),
                ],

                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _busy ? null : _submit,
                    child: _busy
                        ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(_registerMode ? 'יצירת חשבון' : 'כניסה'),
                  ),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () => setState(() { _registerMode = !_registerMode; _err = null; }),
                  child: Text(_registerMode ? 'יש לך חשבון? כנס' : 'אין לך חשבון? הירשם עם קוד גישה'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
