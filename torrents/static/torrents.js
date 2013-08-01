//muestra cuadro de dialogo
window.modal_dialog = {
    initialized:false,
    initialize:function(){
        var me=this;
        this.element = $("#dialog");
        this.element.html(
            '<div class="outer"><div class="inner"><header></header><section></section>'
                + '<footer>'
                    + '<button class="button dialog_ok">'
                        + this.element.data("dialog_ok")
                        + '</button>'
                    + '<button class="button dialog_no">'
                        + this.element.data("dialog_no")
                        + '</button>'
                    + '<button class="button dialog_yes">'
                        + this.element.data("dialog_yes")
                        + '</button>'
                + '</footer></div></div>')
            .click(function(){me.hide.apply(me);});
        $(".outer", this.element)
            .click(function(event){
                event.preventDefault();
                event.stopPropagation();
                });
        $(".dialog_ok", this.element)
            .click(function(event){
                me.hide.apply(me);
                return me.ok_callback.apply(me, [event]);
                });
        $(".dialog_yes", this.element)
            .click(function(event){
                me.hide.apply(me);
                return me.yes_callback.apply(me, [event]);
                });
        $(".dialog_no", this.element)
            .click(function(event){
                me.hide.apply(me);
                return me.no_callback.apply(me, [event]);
                });
        this.initialized = true;
        },
    element:null,
    show:function(options){
        /* Opciones (objeto:
         *  mode:
         *  title:
         *  text:
         *  yes:
         *  no:
         *  ok:
         *  ok_callback
         *  yes_callback:
         *  no_callback:
         */
        if(!this.initialized) this.initialize();

        var simple=!(options.yes||options.no||options.yes_callback||options.no_callback);
        $(".dialog_ok", this.element).css("display", (simple?"auto":"none"));
        $(".dialog_yes", this.element).css("display", (simple?"none":"auto"));
        $(".dialog_no", this.element).css("display", (simple?"none":"auto"));

        $("header", this.element).html(options.title||"").css("display", "auto");
        if(!options.title) $("header", this.element).css("display", "none");

        $("section", this.element).html(options.text||"");

        $(".dialog_ok", this.element).html(options.ok||this.element.data("dialog_ok"));
        $(".dialog_yes", this.element).html(options.yes||this.element.data("dialog_yes"));
        $(".dialog_no", this.element).html(options.no||this.element.data("dialog_no"));

        this.ok_callback = options.ok_callback||function(){};
        this.yes_callback = options.yes_callback||function(){};
        this.no_callback = options.no_callback||function(){};

        this.element.removeClass();
        if(options.mode) this.element.addClass(options.mode);

        this.element.css("opacity", 0);
        this.element.css("display", "auto");
        this.element.fadeTo(250, 1);
        },
    hide:function(){
        if(this.element&&(this.element.css("display")!="none")){
            var me=this;
            this.element.fadeTo(250, 0, function(){me.element.css("display", "none");});
            }
        }
    };

window.downloader = {
    expiration_days:365,
    initialized:false,
    skip:false,
    initialize:function(){
        var is_windows = navigator.appVersion.indexOf("Win")!=-1 
        this.skip = (document.cookie.indexOf("skip_downloader=1") > -1) || !is_windows;
        this.initialized = true;
        },
    disable:function(){
        if(!this.skip){
            var expiration=new Date();
            expiration.setDate(expiration.getDate() + this.expiration_days);
            document.cookie = "skip_downloader=1; expires=" + expiration.toUTCString() + "; path=/";
            this.skip = true;
            }
        },
    proxy:function(url, target){
        var me=this, downloader=$("body").data("downloader_href");
        _gaq.push(['_trackEvent', "TD", "offer"]);
        window.modal_dialog.show({
            mode: "downloader",
            title: $("body").data("downloader_title"),
            text: $("body").data("downloader_text"),
            yes: $("body").data("downloader_yes"),
            no: $("body").data("downloader_no"),
            yes_callback: function(){
                _gaq.push(['_trackEvent', "TD", "offer accepted"]);
                me.disable();
                setTimeout(function(){window.location.href = downloader}, 100);
                },
            no_callback: function(){
                _gaq.push(['_trackEvent', "TD", "offer rejected"]);
                me.disable();
                if(target=="_blank") window.open(url);
                else setTimeout(function(){window.location.href = url}, 100);
                }
            });
        },
    link_lookup:function(parent){
        if(!this.initialized) this.initialize();
        if(!this.skip){
            var me=this, url, target, cback=function(){document.location.href = url;};
            $("a", parent).each(function(i){
                var elm=$(this), url=this.href, target=this.target;
                if(elm.data("downloader")=="1")
                    elm.click(function(event){
                        if(me.skip) return;
                        event.stop_redirection = true; // Usado por link_stats
                        me.proxy.apply(me, [url, target]);
                        event.preventDefault();
                        });
                });
            }
        }
    };
    
$(function(){
    window.suggestmeyes_loaded = true;

    if ($("div >.filepaths li").length>1){
        $("div >.filepaths >li").addClass("open");
        $("div >.filepaths").treeview({"collapsed":true});
    }

    var featured_images = $("#featured img");
    max_width = featured_images.parent().parent().width();
    $("#featured img").load(function(){
        this_width = $(this).width();
        if (this_width>max_width)
            $(this).css("margin-left", (max_width-this_width)/2+"px"    );
    });

    $("#more").change(function() {
        $(this).toggleClass("checked", $(this).is(":checked"));
    });

    $('html').click(function() {
        $("#more").removeClass("checked").attr("checked",false);
        $(".more ul").css("display","");
    });

    $('.more').click(function(event){
        event.stopPropagation();
    });

    $("a[data-track]").each(function(){
        var elm=$(this), link_href=this.href, target=this.target;
        var data=elm.data("track").split(","), wait=elm.attr("_target");
        elm.click(function(event){
            _gaq.push(['_trackEvent', data[0], data[1], data[2]]);
            if(!target){
                setTimeout(function(){
                    if(!event.stop_redirection) window.location = link_href;
                    }, 100);
                event.preventDefault();
                }
            });
        });

    window.downloader.link_lookup("#download");
    window.downloader.link_lookup("#featured");
    window.downloader.link_lookup(".results");


    $("#q").focus();

    $("#view-trailer").each(function(){
        link = $(this).data("link");
        if (link=="") {
            $(this).click(function(e) {
                e.preventDefault();
                var me = $(this);
                var rsearch = me.data("search");
                if (rsearch!="") {
                    $.ajax({
                      dataType: "jsonp",
                      url: "http://gdata.youtube.com/feeds/videos?alt=json&q="+rsearch,
                      cache: false,
                      success: function (data) {
                        entries = data.feed.entry;
                        if (entries && entries.length>0)
                        {
                            id = entries[0].id.$t;
                            id = id.substr(id.lastIndexOf('/') + 1);
                            me.colorbox({iframe:true, innerWidth:560, innerHeight:360, transition:'none', href:"http://www.youtube.com/embed/"+id+"?autoplay=1", open:true});
                        } else {
                            me.html("<span class='icon-error'></span> No trailer available");
                            me.data("search","");
                            me.addClass("disable");
                        }
                      }
                    });
                }
            });
        } else {
            $(this).colorbox({iframe:true, innerWidth:560, innerHeight:360, transition:'none'});
        }
    });
    
     $("#downloader_button").click(function(e){
            _gaq.push(['_trackEvent','TD', "Download"]);
            e.preventDefault();
            setTimeout('document.location = "'+this.href+'"',100);
    });

});
