from uber.tests import *


def test_hours():
    assert Job(start_time=c.EPOCH, duration=1).hours == {c.EPOCH}
    assert Job(start_time=c.EPOCH, duration=2).hours == {c.EPOCH, c.EPOCH + timedelta(hours=1)}


def test_real_duration():
    assert Job(duration=2).real_duration == 2
    assert Job(duration=2, extra15=True).real_duration == 2.25


def test_weighted_hours(monkeypatch):
    monkeypatch.setattr(Job, 'real_duration', 2)
    assert Job(weight=1).weighted_hours == 2
    assert Job(weight=1.5).weighted_hours == 3
    assert Job(weight=2).weighted_hours == 4


def test_total_hours(monkeypatch):
    monkeypatch.setattr(Job, 'weighted_hours', 3)
    assert Job(slots=1).total_hours == 3
    assert Job(slots=2).total_hours == 6


@pytest.fixture
def session(request):
    session = Session().session
    for num in ['One', 'Two', 'Three', 'Four', 'Five', 'Six']:
        setattr(session, 'job_' + num.lower(), session.job(name='Job ' + num))
    for number in ['One', 'Two', 'Three', 'Four', 'Five']:
        setattr(session, 'staff_{}'.format(number).lower(), session.attendee(badge_type=c.STAFF_BADGE, first_name=number))
    request.addfinalizer(session.close)
    return session


class TestAssign:
    @pytest.fixture(autouse=True)
    def default_assignment(self, session):
        assert not session.assign(session.staff_one.id, session.job_one.id)

    def test_non_volunteer(self, session):
        attendee = session.query(Attendee).filter_by(staffing=False).first()
        assert session.assign(attendee.id, session.job_one.id)

    def test_restricted(self, session):
        assert session.assign(session.staff_two.id, session.job_six.id)
        session.staff_two.trusted = True
        session.commit()
        assert not session.assign(session.staff_two.id, session.job_six.id)

    def test_full(self, session):
        assert session.assign(session.staff_two.id, session.job_one.id)

        assert not session.assign(session.staff_three.id, session.job_four.id)
        assert not session.assign(session.staff_four.id, session.job_four.id)
        assert session.assign(session.staff_four.id, session.job_four.id)

    # this indirectly tests the .no_overlap() method, though a more direct test would be good as well
    def test_overlap(self, session):
        assert session.assign(session.staff_one.id, session.job_one.id)
        assert session.assign(session.staff_one.id, session.job_two.id)
        assert session.assign(session.staff_one.id, session.job_five.id)
        assert not session.assign(session.staff_one.id, session.job_three.id)


class TestAvailableStaffers:
    @pytest.fixture(autouse=True)
    def extra_setup(self, session, monkeypatch):
        monkeypatch.setattr(Job, 'all_staffers', [session.staff_one, session.staff_two, session.staff_three, session.staff_four])
        monkeypatch.setattr(Job, 'no_overlap', lambda self, a: True)

        session.staff_one.trusted = session.staff_four.trusted = True

        session.staff_one.assigned_depts = str(c.ARCADE)
        session.staff_two.assigned_depts = str(c.CONSOLE)
        session.staff_three.assigned_depts = '{},{}'.format(c.ARCADE, c.CONSOLE)
        session.staff_four.assigned_depts = '{},{}'.format(c.ARCADE, c.CONSOLE)

    def test_by_department(self, session):
        assert session.job_one.available_staffers == [session.staff_one, session.staff_three, session.staff_four]
        assert session.job_four.available_staffers == [session.staff_two, session.staff_three, session.staff_four]

    def test_by_trust(self, session):
        assert session.job_six.available_staffers == [session.staff_four]

    def test_by_overlap(self, session, monkeypatch):
        monkeypatch.setattr(Job, 'no_overlap', lambda self, a: a in [session.staff_one, session.staff_two])
        assert session.job_one.available_staffers == [session.staff_one]
        assert session.job_four.available_staffers == [session.staff_two]
