"""Okto errors: every error has a code, a message and a fix, in English and Arabic."""

# code: (english message, english fix, arabic message, arabic fix)
MSG = {
    'E001': (
        "unexpected character '{ch}'",
        'remove it, or put it inside a text "..."',
        "حرف غير متوقع '{ch}'",
        'احذفه أو ضعه داخل نص "..."',
    ),
    'E002': (
        'tabs are not allowed for indentation',
        'use 4 spaces instead of the tab',
        'لا يُسمح بعلامة Tab في بداية السطر',
        'استخدم 4 مسافات بدلاً من Tab',
    ),
    'E003': (
        'this indentation does not match any outer block',
        'align this line with an earlier line',
        'إزاحة هذا السطر لا تطابق أي قسم سابق',
        'حاذِ هذا السطر مع سطر سابق',
    ),
    'E004': ('this text is not closed', 'add " at the end of the text', 'هذا النص غير مغلق', 'أضف " في نهاية النص'),
    'E005': ('expected {exp} but found {got}', '{fix}', 'المتوقع {exp} لكن الموجود {got}', '{fix}'),
    'E006': (
        "'{{' inside the text is not closed",
        "add '}}', or write '{{{{' for a literal brace",
        "القوس '{{' داخل النص غير مغلق",
        "أضف '}}' أو اكتب '{{{{' لو تريد القوس نفسه",
    ),
    'E101': ("unknown name '{name}'", '{hint}', "اسم غير معروف '{name}'", '{hint}'),
    'E102': ('expected {exp} but got {got}', '{hint}', 'المتوقع {exp} لكن القيمة {got}', '{hint}'),
    'E103': ("'{name}' cannot be changed", '{hint}', "'{name}' لا يمكن تغييره", '{hint}'),
    'E104': (
        "'{name}' is already defined (line {prev})",
        'choose another name, or assign to it without let/var',
        "'{name}' معرّف من قبل (سطر {prev})",
        'اختر اسماً آخر، أو غيّر قيمته بدون ثابت/متغير',
    ),
    'E105': (
        "'{name}' takes {exp} argument(s) but got {got}",
        'call it like this: {sig}',
        "'{name}' يأخذ {exp} قيمة لكن أُعطي {got}",
        'استدعِه هكذا: {sig}',
    ),
    'E106': ('{what} may be none here', '{fix}', '{what} قد يكون فارغاً هنا', '{fix}'),
    'E107': ("operator '{op}' does not work on {types}", '{hint}', "العملية '{op}' لا تعمل على {types}", '{hint}'),
    'E108': (
        'a condition must be bool but got {got}',
        'compare explicitly, for example: x != 0',
        'الشرط يجب أن يكون منطقياً لكنه {got}',
        'قارن صراحةً، مثال: x != 0',
    ),
    'E109': (
        "function '{name}' may end without returning {ret}",
        'add a return at the end of every path',
        "الدالة '{name}' قد تنتهي بدون إرجاع {ret}",
        'أضف ارجع في نهاية كل مسار',
    ),
    'E110': ("'return' outside a function", 'remove it', "'ارجع' خارج دالة", 'احذفه'),
    'E111': (
        'cannot index {got}; only lists and dicts can be indexed',
        'use a list or a dict here',
        'لا يمكن أخذ عنصر من {got}؛ القوائم والقواميس فقط',
        'استخدم قائمة أو قاموساً هنا',
    ),
    'E112': (
        "cannot infer the type of '{name}'",
        'write the type, for example: let {name}: list[int] = []',
        "لا يمكن استنتاج نوع '{name}'",
        'اكتب النوع، مثال: ثابت {name}: قائمة[عدد] = []',
    ),
    'E113': (
        "'{name}' returns nothing, so its result cannot be used",
        'call it on its own line',
        "'{name}' لا يُرجع قيمة، فلا يمكن استخدام نتيجته",
        'استدعِه في سطر مستقل',
    ),
    'E116': (
        'this value is never none, so the comparison is useless',
        "remove the check, or declare the type with '?'",
        'هذه القيمة لا تكون فارغة أبداً، فالمقارنة بلا فائدة',
        "احذف الفحص، أو عرّف النوع بعلامة '?'",
    ),
    'E117': (
        "the left side of '??' is never none",
        "remove '?? ...'",
        "الطرف الأيسر من '??' لا يكون فارغاً أبداً",
        "احذف '?? ...'",
    ),
    'E118': ("'{kw}' outside a loop", 'remove it', "'{kw}' خارج حلقة", 'احذفه'),
    'E119': (
        'this expression does nothing',
        'assign it to a name, or remove it',
        'هذا التعبير لا يفعل شيئاً',
        'خزّنه في اسم أو احذفه',
    ),
    'E120': (
        "'{fn}' is called here but uses '{name}', which is defined later (line {at})",
        "move the definition of '{name}' above this call",
        "'{fn}' مستدعاة هنا لكنها تستخدم '{name}' المعرّف لاحقاً (سطر {at})",
        "انقل تعريف '{name}' فوق هذا الاستدعاء",
    ),
    'E121': (
        "unknown type '{name}'",
        'use int, float, text, bool, list[T], dict[K, V] or the name of a record',
        "نوع غير معروف '{name}'",
        'استخدم عدد أو عشري أو نص أو منطقي أو قائمة[نوع] أو قاموس[مفتاح، قيمة] أو اسم سجل',
    ),
    'E122': (
        'functions and records must be defined at the top level',
        'move it out of the block',
        'الدوال والسجلات تُعرَّف في المستوى الأعلى فقط',
        'انقلها خارج القسم',
    ),
    'E123': (
        "'{name}' is a built-in name and cannot be redefined",
        'choose another name',
        "'{name}' اسم مبني في اللغة ولا يمكن إعادة تعريفه",
        'اختر اسماً آخر',
    ),
    'E124': (
        'range(...) can only be used in a for loop',
        'write: for i in range(0, 10):',
        'مدى(...) يُستخدم داخل لكل فقط',
        'اكتب: لكل i في مدى(0، 10):',
    ),
    'E125': (
        'only a name, name[index] or name.field can be changed',
        'start from a name defined with var',
        'يمكن تغيير اسم أو اسم[رقم] أو اسم.حقل فقط',
        'ابدأ من اسم معرّف بـ متغير',
    ),
    'E127': ('{what}', '{hint}', '{what}', '{hint}'),
    'E129': (
        "record '{rec}' needs the field '{name}'",
        'add it: {name}: value',
        "السجل '{rec}' يحتاج الحقل '{name}'",
        'أضفه: {name}: قيمة',
    ),
    'E130': ("{what} has no field '{name}'", '{hint}', "{what} ليس فيه الحقل '{name}'", '{hint}'),
    'E132': (
        'dict keys must be text or int, not {got}',
        'use text or int as the key type',
        'مفاتيح القاموس يجب أن تكون نصاً أو عدداً، وليس {got}',
        'استخدم نص أو عدد نوعاً للمفتاح',
    ),
    'E133': (
        "record '{name}' holds itself, so it would never end",
        'make that field optional ({name}?) or a list (list[{name}])',
        "السجل '{name}' يحتوي نفسه، فلن ينتهي أبداً",
        'اجعل ذلك الحقل اختيارياً ({name}?) أو قائمة (قائمة[{name}])',
    ),
    'E134': (
        'this number is too large for an int',
        'the largest whole number is 9007199254740991; write it as a float (add .0) if it can be approximate',
        'هذا الرقم أكبر من أن يكون عدداً صحيحاً',
        'أكبر عدد صحيح هو 9007199254740991؛ اكتبه عشرياً (أضف .0) لو التقريب مقبول',
    ),
    'E140': (
        'this program is not allowed to {what}',
        'add at the top of the file: {example}',
        'هذا البرنامج غير مسموح له بـ{what}',
        'أضف في أعلى الملف: {example}',
    ),
    'E141': (
        'a secret cannot be shown or turned into text',
        'compare it with secret_equals(secret, text); use reveal(secret) only where the real value must leave',
        'السر لا يُعرض ولا يتحول إلى نص',
        'قارنه بـ سر_يساوي(السر، النص)؛ واستخدم اكشف(السر) فقط حيث يجب أن تخرج القيمة الحقيقية',
    ),
    'E142': (
        'the query must be written here as a text, not taken from a value',
        'write: sql("select ... where id = {{value}}")   values inside {{ }} are sent separately and can never change the query',
        'الاستعلام يجب أن يُكتب هنا نصاً، لا أن يؤخذ من قيمة',
        'اكتب: استعلام("select ... where id = {{القيمة}}")   القيم داخل {{ }} تُرسل منفصلة ولا تغيّر الاستعلام أبداً',
    ),
    'E143': (
        "'allow' lines must be at the top level",
        'move it to the top of the file',
        "أسطر 'اسمح' تكون في المستوى الأعلى فقط",
        'انقله إلى أعلى الملف',
    ),
    'E144': (
        "unknown permission '{name}'",
        'use one of: read, write, env, serve',
        "صلاحية غير معروفة '{name}'",
        'استخدم واحدة من: قراءة، كتابة، بيئة، استضافة',
    ),
    'E145': (
        'serve needs the name of a function that takes a Request and returns a Response',
        'write: fn handle(req: Request) -> Response:   then: serve("127.0.0.1:8080", handle)',
        'الاستضافة تحتاج اسم دالة تأخذ طلباً وترجع استجابة',
        'اكتب: دالة تعامل(ط: طلب) -> استجابة:   ثم: استضف("127.0.0.1:8080"، تعامل)',
    ),
    'E146': (
        'serve(...) must be the last line of the program, at the top level',
        'move it to the end of the file, outside any function or block; nothing after it would run',
        'استضف(...) يجب أن يكون آخر سطر في البرنامج، في المستوى الأعلى',
        'انقله إلى آخر الملف، خارج أي دالة أو قسم؛ لن يعمل شيء بعده',
    ),
    'E147': (
        'the html must be written here as a text, not taken from a value',
        'write: html("<p>{{value}}</p>")   values inside {{ }} are escaped, so they can never add tags or scripts',
        'صفحة الويب يجب أن تُكتب هنا نصاً، لا أن تؤخذ من قيمة',
        'اكتب: صفحة_ويب("<p>{{القيمة}}</p>")   القيم داخل {{ }} تُهرَّب فلا تضيف وسوماً أو سكربتات أبداً',
    ),
}


def _pick(v, lang):
    if isinstance(v, tuple) and len(v) == 2:
        return v[0] if lang == 'en' else v[1]
    return v


class OktoError(Exception):
    def __init__(self, code, line, col, **args):
        super().__init__(code)
        self.code, self.line, self.col, self.args_ = code, line, col, args

    def parts(self, lang='en'):
        m = MSG[self.code]
        a = {k: _pick(v, lang) for k, v in self.args_.items()}
        if lang == 'en':
            return m[0].format(**a), m[1].format(**a)
        return m[2].format(**a), m[3].format(**a)

    def as_dict(self, lang='en'):
        msg, fix = self.parts(lang)
        return {'code': self.code, 'line': self.line, 'col': self.col, 'message': msg, 'fix': fix}

    def render(self, path, lines, lang='en'):
        msg, fix = self.parts(lang)
        head = 'error' if lang == 'en' else 'خطأ'
        fixw = 'fix' if lang == 'en' else 'الحل'
        out = ['%s[%s] %s:%d:%d' % (head, self.code, path, self.line, self.col)]
        if 1 <= self.line <= len(lines):
            num = '%5d' % self.line
            out.append('%s | %s' % (num, lines[self.line - 1]))
            out.append('%s | %s^' % (' ' * 5, ' ' * max(0, self.col - 1)))
        out.append('  ' + msg)
        out.append('  %s: %s' % (fixw, fix))
        return '\n'.join(out)
