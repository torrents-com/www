;(function($) {
    $.cookiesLaw = {
        accepted: false,
        hide_msg: false,
        start_call: function() {},
        initialize:function(domains, start_call) {
            // Save local variables
            this.start_call = start_call;
            this.domains = domains;

            // Check local cookie
            var cookie_level = $.cookie("cookie_level");
            this.accepted = cookie_level>0;
            this.hide_msg = cookie_level>1;

            // If accepted, start and exit
            if (this.accepted) {
                this.final_process();
                return;
            }

            this.visit_domains("notify", function(){
                $.cookie("cookie_level", $.cookiesLaw.hide_msg?2:1, {expires: 3650, path: '/' });
                $.cookiesLaw.final_process();
            });
        },
        visit_domains: function(action, after) {
            // Check geolocation and set cookie for all domains
            var requests = []
            for (var i = 0; i < this.domains.length; i++) {
                requests.push($.ajax({
                    type: 'GET', url: this.domains[i]+"?"+action,
                    async: true, contentType: "application/json", dataType: 'jsonp',
                    success: function(response) {
                        if (response>0) {
                            $.cookiesLaw.accepted = true;
                            if (response>1) {
                                $.cookiesLaw.hide_msg = true;
                            }
                        }
                    }
                }));
            }

            // Show alert when finish or run scripts
            $.when.apply($,requests).done(after);
        },
        final_process: function() {
            if (this.accepted)
                this.start_call();

            if (!this.hide_msg) {
                $(function(){
                    show_alert("<a href='#' id='cookies_accept'>aceptar</a><p>Utilizamos cookies para mejorar nuestros servicios. Si continúa navegando, consideramos que acepta su uso. <br/>Para más información haz click <a id='cookies_info' href='#'>aquí</a>.", "info");
                    $("#cookies_accept").click(function(event){
                        event.preventDefault();
                        $.cookie("cookie_level", 2, {expires: 3650, path: '/' });
                        $.cookiesLaw.visit_domains("accept", function(){
                            window.location.reload();
                        });
                    });
                    $("#cookies_info").click(function(event){
                        event.preventDefault();
                        $.cookiesLaw.showMoreInfo();
                    });
                });
            }
        },
        showMoreInfo: function() {
            $.colorbox({html:this.legend, width:"50%",close:"cerrar"});
        },
        legend:"<div class='text_page'><h2>Condiciones</h2><p>Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>\
        <p>Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur?</p>\
        <p>But I must explain to you how all this mistaken idea of denouncing pleasure and praising pain was born and I will give you a complete account of the system, and expound the actual teachings of the great explorer of the truth, the master-builder of human happiness. No one rejects, dislikes, or avoids pleasure itself, because it is pleasure, but because those who do not know how to pursue pleasure rationally encounter consequences that are extremely painful. Nor again is there anyone who loves or pursues or desires to obtain pain of itself, because it is pain, but because occasionally circumstances occur in which toil and pain can procure him some great pleasure. To take a trivial example, which of us ever undertakes laborious physical exercise, except to obtain some advantage from it? But who has any right to find fault with a man who chooses to enjoy a pleasure that has no annoying consequences, or one who avoids a pain that produces no resultant pleasure?</p>\
        <p>At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est, omnis dolor repellendus. Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus, ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat.</p></div>"
    };
})(jQuery);
