def test_employee_ticket_flow_and_rbac(client, employee_headers):
    login = client.post(
        "/v1/auth/login",
        json={"email": "employee@pulse.local", "password": "employee123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "employee"

    me = client.get("/v1/me", headers=employee_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "employee"

    enhanced = client.post(
        "/v1/ai/enhance-ticket-description",
        headers=employee_headers,
        json={"originalText": "vpn отваливается   несколько раз в день"},
    )
    assert enhanced.status_code == 200
    enhanced_body = enhanced.json()
    assert enhanced_body["aiEnhanced"] is True
    assert enhanced_body["enhancedText"].startswith("[AI-enhanced]")

    created = client.post(
        "/v1/tickets",
        headers=employee_headers,
        json={
            "title": "VPN disconnects during the day",
            "description": enhanced_body["enhancedText"],
            "originalDescription": enhanced_body["originalText"],
            "aiEnhanced": True,
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    assert created_body["groupId"] == "grp_vpn_access"
    assert created_body["status"] == "in_review"
    assert len(created_body["history"]) == 2

    my_tickets = client.get("/v1/tickets/my?query=vpn&status=in_review", headers=employee_headers)
    assert my_tickets.status_code == 200
    list_body = my_tickets.json()
    assert list_body["meta"]["totalItems"] >= 2
    assert all(item["status"] == "in_review" for item in list_body["items"])

    detail = client.get(f"/v1/tickets/my/{created_body['id']}", headers=employee_headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["author"]["id"] == "usr_employee_demo"
    assert detail_body["originalDescription"] == enhanced_body["originalText"]

    forbidden = client.get("/v1/manager/ticket-groups", headers=employee_headers)
    assert forbidden.status_code == 403

    foreign = client.get("/v1/tickets/my/tkt_foreign", headers=employee_headers)
    assert foreign.status_code == 404


def test_manager_group_comment_status_and_analytics(client, manager_headers, employee_headers):
    login = client.post(
        "/v1/auth/login",
        json={"email": "manager@pulse.local", "password": "manager123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "manager"

    me = client.get("/v1/me", headers=manager_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "manager"

    groups = client.get("/v1/manager/ticket-groups?query=vpn&status=in_review", headers=manager_headers)
    assert groups.status_code == 200
    groups_body = groups.json()
    assert groups_body["meta"]["totalItems"] >= 1
    group_id = groups_body["items"][0]["id"]

    comment = client.put(
        f"/v1/manager/ticket-groups/{group_id}/comment",
        headers=manager_headers,
        json={"managerComment": "Shared VPN issue identified. Rolling out a fix."},
    )
    assert comment.status_code == 200
    assert comment.json()["managerComment"] == "Shared VPN issue identified. Rolling out a fix."

    status = client.patch(
        f"/v1/manager/ticket-groups/{group_id}/status",
        headers=manager_headers,
        json={"status": "resolved"},
    )
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["status"] == "resolved"
    assert all(ticket["status"] == "resolved" for ticket in status_body["relatedTickets"])

    employee_ticket = client.get("/v1/tickets/my/tkt_seed_pt_122", headers=employee_headers)
    assert employee_ticket.status_code == 200
    employee_ticket_body = employee_ticket.json()
    assert employee_ticket_body["status"] == "resolved"
    assert employee_ticket_body["managerComment"] == "Shared VPN issue identified. Rolling out a fix."
    assert employee_ticket_body["resolvedAt"] is not None
    assert any(event["type"] == "manager_comment_updated" for event in employee_ticket_body["history"])
    assert any(event["type"] == "group_status_changed" for event in employee_ticket_body["history"])

    analytics = client.get("/v1/manager/analytics/summary", headers=manager_headers)
    assert analytics.status_code == 200
    analytics_body = analytics.json()
    assert analytics_body["groupsByStatus"]["resolved"] >= 1
    assert analytics_body["ticketsByStatus"]["resolved"] >= 1


def test_auth_errors(client):
    login = client.post(
        "/v1/auth/login",
        json={"email": "employee@pulse.local", "password": "wrong-password"},
    )
    assert login.status_code == 401

    unauthorized = client.get("/v1/me")
    assert unauthorized.status_code == 401
    body = unauthorized.json()
    assert body["error"]["code"] == "unauthorized"
