from backend.security import hash_password, verify_password


class TestPasswordHashing:
    def test_correct_password_verifies(self):
        password_hash = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", password_hash) is True

    def test_wrong_password_does_not_verify(self):
        password_hash = hash_password("correct horse battery staple")
        assert verify_password("wrong password", password_hash) is False

    def test_hash_is_not_the_plaintext_password(self):
        assert hash_password("correct horse battery staple") != "correct horse battery staple"

    def test_same_password_hashes_differently_each_time(self):
        # argon2 salts every hash -- two hashes of the same password must
        # never be equal, or a leaked hash table would reveal which
        # accounts share a password.
        assert hash_password("shared-password") != hash_password("shared-password")

    def test_garbage_hash_does_not_verify_and_does_not_raise(self):
        assert verify_password("anything", "not-a-real-argon2-hash") is False
